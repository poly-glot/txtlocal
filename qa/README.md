# QA against a running stack

Five scripts, in the shape of the `shorten` repo's own `qa/`: each prints one `ok` or `FAIL` line per
assertion and **exits non-zero if any assertion failed** — exit 1 is a broken stack, exit 2 is a broken
invocation (a missing argument, a tool that is not installed, no credentials).

They exist because `scripts/check.sh`'s 1226 tests and `scripts/smoke.py`'s end-to-end run all execute
inside one process, or against a `TestClient` that never opens a real socket. Four things about this
design cannot be settled that way, and they are listed at the end of this file with the script that
closes each.

**`01-routing.py`, `02-negative.py`, `03-idempotency.py` and `04-load.py` have all been run against the
local stack (`scripts/dev.sh`) on 2026-09-20, and all four pass.** `05-cost.sh` has been written and its
argument handling exercised; its AWS calls have not, because nothing is deployed — see the note in its
own `--help` text and in [Open questions](#open-questions) below.

## Running them

`uv run python qa/01-routing.py`, and so on for `02` and `03`. `04-load.py` and `05-cost.sh` take the
same shape, `bash` and the AWS CLI v2 for `05-cost.sh` only.

```bash
scripts/dev.sh &                      # or use the stack you already have running

uv run python qa/01-routing.py
uv run python qa/02-negative.py
uv run python qa/03-idempotency.py
uv run python qa/04-load.py --rate 20 --duration 15
qa/05-cost.sh                         # only once txtlocal is actually deployed
```

That is the order the failures are most useful in: routing and negative paths before the two that cost
real time, idempotency before load, load before cost. Every script takes `--base-url` (default
`http://127.0.0.1:9000`), `--user` (default `demo@txtlocal.local`) and `--operator-secret` (default
`local-operator-secret`, matching `wiring.py`'s own local default) — point `--base-url` at a deployed
function URL once one exists, and pass the real `OPERATOR_SECRET` from wherever it was generated.

In CI, run `01` through `04` under `set -e` in that order and let the first non-zero exit stop the job.
`05-cost.sh` only makes sense post-deploy, so it is not part of that chain.

## What each script proves, and what a failure means

### `01-routing.py` — the phase-7 operator and email wiring, over the wire

Registers two websites, approves one and rejects the other through the **operator router directly**,
bypassing the dashboard, then registers an allowed email address and fires the demo inbound-email
endpoint both from that address and from an unregistered one.

| Assertion | What a failure means |
|---|---|
| both websites start `UNDER_REVIEW` | `register_websites` stopped defaulting new rows to the review state |
| the operator-approved website reads `APPROVED` | the operator router, the HMAC secret check, or `approve_website_now` broke after the last deploy |
| the operator-rejected website reads `REJECTED` with its reason echoed | same, for `reject_website` |
| a matched inbound email queues exactly one SMS | the `EmailSender` GSI1 lookup (`repo.email_senders_by_address`) is broken — this exact path had no index at all before phase 7 and the lookup was structurally impossible; this assertion is what would have caught it |
| an unmatched sender queues nothing | `handle_inbound_email` stopped refusing silently and either raised or sent anyway |

Everything it creates it deletes, except the two websites: there is no delete endpoint for a
registered website, so they accumulate under the signed-in demo account's own review list. Harmless,
and worth knowing before wondering why "Website Registration" grows a row per run.

### `02-negative.py` — the refusals a live server gives, not a `TestClient`

Hits the operator router with no, wrong, and finally the right secret; hits an unauthenticated
dashboard route; hits `/api/app/session` with the wrong verb.

| Assertion | What a failure means |
|---|---|
| no or wrong `X-Operator-Secret` → 401, the fixed sentence | `hmac.compare_digest` stopped gating the operator router, or `wiring.py` stopped reading `OPERATOR_SECRET` |
| the right secret still 404s an unknown account/domain | the operator router's own error mapping broke, separately from its auth |
| the wrong HTTP verb answers 404, not 405 | this is this app's actual, verified behaviour, recorded here rather than assumed — CLAUDE.md section 4 lists no 405 at all, and this confirms nothing emits one by accident |
| no bearer token → 401 | a dashboard route stopped requiring `authenticated` |

### `03-idempotency.py` — the race `smoke.py` cannot reach

`developer/router.py`'s `idempotent()` claims an `Idempotency-Key` with a conditional write and falls
back to a `Conflict` when the claim is lost to a request still in flight. `scripts/smoke.py` proves the
**sequential** replay (send, then resend) — a single event loop can prove that much on its own. This
script fires eight genuinely concurrent requests, on eight real sockets, with the identical key and
body, through an `httpx.AsyncClient`.

| Assertion | What a failure means |
|---|---|
| exactly one request actually sends | the conditional write in `begin_idempotency` is not exclusive: two concurrent callers both believe they won the claim, and the account is charged twice for one message |
| every response is 201 or 409, nothing else | a race is surfacing as a 500 instead of the designed `Conflict` |
| the balance moves by exactly one message's cost | the same failure, confirmed from the money rather than the status code |
| history carries exactly one matching message | the same failure, confirmed from the row count |

Run on this machine on 2026-09-20: one 201, seven 409s. All seven lost the claim before the winner
finished, so none exercised the replay branch — a slower `fake` send, or a real network round trip in
`live` mode, would let some of the eight land after the winner and come back as a replay instead. Both
outcomes are correct; this run only exercised one of the two.

### `04-load.py` — the load smoke on the one path three apps share

20 requests a second for 15 seconds at one tracked link's redirect, the path CLAUDE.md section 7 calls
out by name: "exactly one eventually consistent `GetItem` and nothing else." No `vegeta` or `k6`: an
`asyncio`-paced `httpx.AsyncClient` is enough at this rate and keeps the only dependency one this repo
already has approved.

| Assertion | What a failure means |
|---|---|
| success ratio ≥ 0.999 | the redirect path cannot hold 20 rps even alone on a laptop, which is a bad sign for sharing 25 units with `donation` and `shorten` in production |
| zero 5xx responses | the same, read from status codes rather than a ratio |
| p99 under 500 ms | a regression in the "one `GetItem`" design, e.g. a second round trip crept in |

**Not asserted: table throttles.** `scripts/local-table.sh` creates the local table
`PAY_PER_REQUEST`, not the shared account's provisioned 25/25 units, so a genuine
`ProvisionedThroughputExceededException` cannot be produced here even by a broken deploy. This is
[open question 1](#open-questions).

Run on this machine on 2026-09-20: 300/300 succeeded, p50 9 ms, p99 29 ms.

### `05-cost.sh` — the cost checklist

Ten-odd assertions, each a real AWS call, in the exact shape of `shorten/qa/07-cost.sh`: the shared
table's provisioned capacity, every function outside a VPC, every function's log group with an
explicit retention, and the three budgeted alarms named in `docs/architecture.md` section 2
(`txtlocal-api-errors`, `txtlocal-send-dlq`, `txtlocal-rollup-failed`). The full list and the
arithmetic behind it is in [`COST.md`](COST.md).

**Not run.** txtlocal has no `aws-cloud` pull request yet and nothing deployed — the AWS hold is a
standing instruction for this project, not an oversight. `--help`, `--account`, `--table`,
`--functions` and the unknown-argument refusal have all been exercised locally; every `aws` call has
not.

## Open questions

| # | Question | Closed by |
|---|---|---|
| 1 | Does the deployed, provisioned, 25/25-unit shared table throttle under real load the way the on-demand local table structurally cannot? | not yet — re-run `04-load.py` against the deployed stack, watching `ReadThrottleEvents` on `aws-cloud`, before trusting the "zero throttles" half of this suite |
| 2 | Does a concurrent idempotency race ever land on the replay branch rather than the conflict branch, and does that branch return byte-identical bodies to the winner? | partially — `03-idempotency.py`'s one run so far only produced conflicts; re-run with a slower send (or in `live` mode) to force some requests past the winner's finish and exercise the replay path |
| 3 | Do the three alarms in `docs/architecture.md` actually exist post-deploy with the names this suite assumes? | `05-cost.sh`, once there is something to point it at |
| 4 | Is every Lambda's log group given an explicit retention at all, given no day count is written down anywhere in this repo the way `shorten`'s 90-day S3 lifecycle is? | `05-cost.sh` only asserts a retention is *set*, not a specific number — decide and record one in `docs/architecture.md` before this can assert more |

## Housekeeping

`01-routing.py` and `03-idempotency.py` create their fixtures through the API; `01` deletes its email
address fixture in-line and leaves its two website fixtures behind (no delete endpoint exists).
`04-load.py` creates one tracked link and never deletes it — tracked links have no delete endpoint
either, and a handful of extra rows over the link's own TTL is not worth building one for. Nothing here
reads or writes another application's rows: the IAM fence is `dynamodb:LeadingKeys` on `txtlocal#*`.
