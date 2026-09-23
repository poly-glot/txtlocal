# txtlocal: Python on Lambda

An SMS platform: GBP balance, contacts and lists, senders, quick SMS and campaigns, a two-way inbox,
automation rules, a developer API with webhooks, Stripe billing, usage counted from logs. Python 3.14 on
Lambda, one shared DynamoDB table, React on CloudFront, AWS End User Messaging behind one port. This file
is the rules and the reasons behind them; it binds every session and every subagent.

Read in this order before changing behaviour: `docs/architecture.md` (the fifteen decisions and the
Lambda map), `specs/01-dynamodb-data-model.md` (keys, flows, every deliberate ceiling), the slice's
section of `specs/03-features.md` (what the screens require), `specs/02-sms-gateway.md` when the change
touches sending, `specs/04-developer-api.md` when it touches `/api/v3`, `docs/testing.md` before writing
a test, `frontend/CLAUDE.md` before touching `frontend/`, `docs/runbook.md` before an actual deploy or
an SMS-mode change. `tasks/plan.md` is the build order and `tasks/lessons.md` is the mistake register;
read the lessons at the start of every session. The AWS resources live in the shared `aws-cloud`
repository under its $5-a-month ceiling; this repository deploys code only. `qa/` holds the scripts
that prove the deployed stack, not just the code, per `qa/README.md`.

## 1. Invariants

These hold on every change, whatever the task.

- Never build a `PK`, `GSI1PK` or `GSI2PK` value by hand. Every partition key goes through
  `shared.table.partition`, whose `txtlocal#` prefix is what the platform's `dynamodb:LeadingKeys` fence
  matches; a key assembled inline does not read the wrong rows, it fails closed with access denied.
- Every SMS leaves through `messaging.gateway.SmsGateway` after `messaging.policy.SendPolicy` has
  allowed it. No other module constructs a `pinpoint-sms-voice-v2` client, and `SMS_MODE` is read in
  `entrypoints/wiring.py` and nowhere else. This is what makes `fake`, `dryrun`, `sandbox` and `live`
  one code path.
- Logs, metrics and error messages never carry a phone number, a message body, an email address, an
  API key, a Stripe key or a Cognito token. Fields carry ids, country codes, outcomes and counts:
  `account_id`, `message_id`, `campaign_id`, `country`, `status`, `outcome`, `error`. The usage rollup
  reads these logs, so a log line is also a ledger of what was sent; keep the field names stable.
- A message id is minted with `messaging.model.uuid7_at(now, rng)`, never a bare `uuid7()`: the row's
  sort key is the id's own millisecond, which is what makes reading one message by id a single `GetItem`
  rather than a query. Every other id is `str(uuid.uuid7())`.
- Money is integer micro-pounds in a field named `*_micro`. Stripe speaks pence; convert at the Stripe
  boundary in `billing/gateway.py` and nowhere else. Never a `float` near money.
- A balance changes only inside `billing.service` through a conditional update or a transaction that
  also writes the ledger row. No other slice touches `balance_micro`; it asks billing to reserve,
  settle or refund.
- No scans and no N+1 reads: the role does not grant `Scan`, and a request does a bounded number of
  round trips by design. A campaign loads the opt-out list once into a set, never once per recipient.
- Every loop over the network is bounded and every retry sleeps a jittered interval from
  `shared.table.backoff`, never a fixed one. A bounded loop that exhausts raises `Internal`.
- One event loop per process, owned by `shared.runtime`. Entrypoints call `runtime.run(coro)`; nothing
  calls `asyncio.run` or creates a loop, so `aioboto3` clients survive warm invocations. Never
  `create_task` fire-and-forget in a handler: the sandbox freezes when the response returns and the task
  dies silently.
- Every worker action is safe to repeat, because SQS and SNS deliver at least once. Idempotency lives
  in the conditional write, never in a "have I seen this" set in memory.
- Conditional writes return `bool` through `shared.table.condition_failed_as_false`; `False` means the
  condition was lost and is never an exception.
- Never `ADD` on a nested path. DynamoDB Local accepts `ADD counts.sent :1`, the current AWS docs no
  longer forbid it and older ones did, so the one form we can rely on is
  `SET #counts.#sent = if_not_exists(#counts.#sent, :zero) + :one`, which the docs document for
  nested maps. A row whose nested counters are updated is created with the parent map present, or
  the update raises a validation error. Top-level `ADD` is unambiguous and stays.
- No new dependency, and no new extra on an existing one, without asking first. The approved runtime
  list is `aioboto3`, `fastapi`, `httpx`, `mangum`, `phonenumbers`, `pydantic`, `PyJWT[crypto]`; the
  approved development list is `import-linter`, `mypy`, `pytest`, `pytest-asyncio`, `ruff`,
  `types-aioboto3`. Check `uv.lock` before assuming something is missing.
- No comments of any kind: no `#` lines, no docstrings, no `TODO`. `examples/raffle_draw.py` explains
  itself in a docstring; here that paragraph belongs in the spec. Rationale lives in this file,
  `docs/`, or `specs/`. Names and shape are the only explanation the reader gets, so spend the effort
  there. A `# type: ignore` is a comment; use `typing.cast` or fix the type.
- The alarm budget is three and all three are in use; a new alarm means removing one or asking. The
  custom metric budget is zero.
- A change to a queue, a topic, a schedule, a function URL, an IAM policy, a Cognito setting or an
  environment variable is a pull request to `aws-cloud`, never to this repository. Reading an
  environment variable that was never set is a cold-start failure; add it there first.
- Secrets enter as function environment and are read once in `entrypoints/wiring.py`.
- A stored value the server only ever compares — an API key, a password — is hashed and the
  plaintext is never kept. A stored value the server must produce output from later — a webhook
  signing secret, used as HMAC input on every delivery — cannot be hashed, because hashing it makes
  signing impossible; it stays plaintext at rest and is shown once at creation, exactly like a
  third-party secret such as `STRIPE_WEBHOOK_SECRET`. Know which kind a new secret is before
  choosing how to store it.
- The local sign-in provider is fenced to a laptop. `identity.dev_idp` accepts any address in
  `DEV_IDP_USERS` without a password and signs tokens with a key it makes at start-up, so
  `wiring.dev_idp` refuses to build it unless `AWS_ENDPOINT_URL_DYNAMODB` is set, which no
  deployed function does. Never widen that condition; a deployed stack verifies Cognito's JWKS.

## 2. Code shape

- A function tells one story and its body reads as paragraphs: a blank line between steps, each
  paragraph one step, load, check, decide, write. The moment a paragraph needs a name to be understood
  it becomes a function carrying that name.
- Guards first, happy path flat. After the early raises the main flow runs at one level of
  indentation; a third level is the signal to extract.
- Wire models are pydantic, `class X(Model)` from `shared.model`, camelCase on the wire and snake_case
  in code through the alias generator. Internal values are `@dataclass(frozen=True, slots=True)`.
  States are `StrEnum` with `SCREAMING_SNAKE_CASE` values, and every dispatch on one is a `match` with
  `assert_never` in the last arm, never an `if` ladder: a new state must fail type checking at every
  point that cares.
- Ports are `typing.Protocol`: `Repo` classes, `SmsGateway`, `Bus`, `PaymentGateway`, `Clock`. A
  service is a frozen dataclass holding its ports, with `clock` and `rng` injected the way
  `DrawService` does, so a test passes a fixed clock and a seeded `Random`.
- A rule the spec states gets a module-level pure function named for it: `is_within_trial`,
  `segments_of`, `is_opted_out`. The spec sentence and the code share a name, and a search for either
  finds the other.
- A DynamoDB condition or update expression is a module constant whose name says what it guards:
  `IF_ABSENT`, `CLAIM_SCHEDULED`, `DEBIT_IF_COVERED`. A literal inside a call has no name and therefore
  no reason.
- Enumerate, never repeat. N things handled the same way are one `StrEnum` and one exhaustive `match`
  per behaviour; `automation.RuleAction` is the shape. No parallel lists that must agree.
- Reach for the language before a helper: `match`, `walrus` in a guard, `itertools.batched` for SQS
  batches of ten, `functools.partial` for a clock, `operator.attrgetter` for a sort key,
  `dict.setdefault` and `Counter` for tallies, `str.removeprefix`, `datetime.now(UTC)`.
- No `Any`, no untyped `dict` crossing a function boundary. A boto3 response is typed through
  `types-aioboto3` and narrowed at the edge of the repository method that received it.
- Alphabetical wherever there is no meaningful order: `StrEnum` members, dataclass fields, pydantic
  fields, imports inside a `from` line, keyword arguments in a call, keys in a literal. A fixed order
  makes a diff show what changed.
- Hoist invariants out of loops; membership is a `set` or `dict`, never `in list`.

## 3. Ownership and slices

- Ten vertical slices under `src/txtlocal/slices/`: `identity`, `billing`, `contacts`, `senders`,
  `messaging`, `campaigns`, `inbox`, `automation`, `developer`, `analytics`. A slice is `model.py`,
  `repo.py`, `service.py`, `router.py`, `tests/`. Another slice imports `service.py` and `model.py`
  only, plus messaging's three public rule modules, `gateway`, `policy` and `segments`;
  `import-linter` enforces it and `scripts/check.sh` runs it.
- A type lives once, in the slice that owns it. A second slice imports it and never redeclares a copy.
  A type two slices need but neither owns is a sign the boundary is wrong; ask before moving it to
  `shared`.
- `shared/` holds what every slice needs and no slice owns: `errors`, `model`, `table`, `telemetry`,
  `runtime`, `clock`, `money`, `phone`, `testing`. It grows by asking, not by convenience.
- `entrypoints/` is one module per Lambda plus `wiring.py`, the only composition root. An entrypoint is
  the runtime boundary and nothing else: it parses the event, calls one service, maps the outcome.
  Handlers are importable and callable from a test without Lambda.
- Every `DynamoRepo` method sits in the slice whose rows it reads, so what this app does to the table
  is enumerable by reading ten `repo.py` files.
- A slice's `router.py` exposes one factory, `build_router(service, authenticated) -> APIRouter`, whose
  routes close over the service they were given; a slice with a developer face exposes
  `build_public_router(service, api_user)` as well. `identity.service` owns the two dependencies,
  `authenticated` for `/api/app` and `api_user` for `/api/v3`, and every other slice takes them as
  parameters. No slice reads `request.app.state`, imports `entrypoints`, or constructs an adapter: a
  test builds the router with in-memory services and a `TestClient`, and `wiring.py` builds it with
  the real ones.
- An entrypoint that publishes to the bus calls `wiring.register_handlers()` before it builds its
  service. `LocalBus` dispatches in the process that publishes, so a process that never registers
  the handlers raises on the first `send`; the scheduler ran as its own process and did exactly
  that, claiming a campaign and then dying with the money already reserved.
- Work leaves a request through `shared.bus.Bus`: `send(queue, messages)` for SQS work and
  `publish(topic, body)` for provider-shaped events. `LocalBus` runs the registered handler in-process
  before the call returns; `SqsBus` sends to SQS and publishes to SNS. A message body is the JSON of a
  pydantic model the consuming entrypoint owns.

## 4. Errors

- `shared.errors.AppError` is the one fallible-API type: `BadRequest` 400, `Unauthorized` 401,
  `PaymentRequired` 402, `Forbidden` 403, `NotFound` 404, `Conflict` 409, `RateLimited` 429,
  `Internal` 500, `Upstream` 502, `GatewayTimeout` 504. Guards raise the specific one; `entrypoints/api.py` maps it to HTTP in
  one exception handler and nowhere else.
- `public_message` never leaks an internal detail: `Internal` and `Upstream` answer a fixed sentence.
  A `BadRequest` message is user-facing copy, rendered verbatim by the page, so the server owns the
  wording and a test asserts it.
- `botocore.exceptions.ClientError` is caught only in `shared.table`, where a lost condition becomes
  `False` and everything else becomes `AppError.Internal` carrying the error code. Never stringify an
  error early.
- A Stripe webhook answers 200 for every terminal outcome so Stripe stops redelivering, and 500 only
  for an error Stripe should retry.
- An SQS handler reports partial batch failures through `batchItemFailures`; a message that fails
  three times lands on the dead-letter queue, which is what the alarm watches. Raising for the whole
  batch re-sends the nine that succeeded.
- Never swallow a failure on the table, payment or send path with `except Exception: pass`,
  `contextlib.suppress`, or a default. Defaulting an absent request header to empty is fine, because
  the check that follows rejects it.

## 5. Async and the Lambda runtime

- Handlers do their work inline and return. CPU work here is HMAC and hashing, microseconds; if real
  CPU work ever arrives, `asyncio.to_thread` it.
- Clients are created once per process in `wiring.py` inside the shared loop and reused. A client
  created per request is a TLS handshake per request.
- Every loop over the network is bounded: DynamoDB paging by `LastEvaluatedKey` with a page cap, the
  send worker by its batch, the Athena and Logs Insights polls by a deadline, the fan-out by the list
  size. Concurrency inside a worker is `asyncio.gather` over a batch of at most ten, never unbounded.
- The send worker's event source mapping has maximum concurrency 2 and the table has 25 shared write
  units. Keep the pacing: an unbounded sender is how one app throttles the other two.

## 6. Tracing, logging and metrics

- `shared.telemetry.configure()` runs first in every entrypoint; output is one JSON object per line
  with the event fields at the top level. Log through `telemetry.log(event, **fields)`, never `print`
  or a bare `logging.info` with a formatted string: the rollup queries these lines by field name.
- The two lines analytics depends on are `event=message_accepted` from `send-worker` and
  `event=api_request` from `api`. Their fields are named in `specs/05-analytics.md`; renaming one is a
  change to the rollup query in the same commit.
- A handler that answers 5xx logs it at error level with a `status` field.
- No custom metrics. The three alarms watch metrics AWS publishes.

## 7. Performance and capacity

- Every DynamoDB round trip is latency and a slice of 25 units shared with two other apps. The O(1)
  shapes are the design: one query answers a history page, one query answers a conversation, one
  conditional update settles a delivery event, one `BatchGetItem` answers a reporting window.
- The redirect path is exactly one eventually consistent `GetItem` and nothing else; CloudFront caches
  the answer. Clicks are counted from logs, never in the request.
- Send jobs write at most three items per message: the message row and its sent marker in one
  transaction, then the campaign counter. Anything more is a design change.
- 256 MB arm64; keep imports lean and lazy where a module is used by one path. Cold start is a user
  waiting for the dashboard; the whole stack must fit 400k GB-seconds a month with two other apps.

## 8. Testing and linting

- `docs/testing.md` binds exactly as this file does. Pure rules get table-driven tests beside them
  with an `id` per case; anything touching the table gets an integration test through
  `shared.testing.local_repo`, which skips itself when `AWS_ENDPOINT_URL_DYNAMODB` is unset; gateways
  and buses get an in-memory reference implementation with the same conditional semantics.
- A test asserts one behaviour and its name says which. Assert the error type, never `raises
  Exception`; assert the message verbatim; test every ceiling on both sides.
- A bug fix lands with the test that would have caught it, in the same change.
- `scripts/check.sh` is the gate: `ruff format --check`, `ruff check`, `mypy --strict`, `lint-imports`,
  `pytest`. It runs as the pre-commit hook and in CI on every pull request and push, with DynamoDB
  Local so the integration tests run rather than skip. Nothing is done until it is green, and the
  report pastes its last lines.
- Never `# noqa`, `# type: ignore` or `# pragma`. They are comments and they are debt; fix the code or
  change the rule in `pyproject.toml` in its own change with the reason in the commit message.

## 9. Tooling and token discipline

- No Python and no Node on the host. Everything runs in the dev container: `uv sync`, `uv run
  scripts/check.sh`, `pnpm --dir frontend check`. Off-container, `docker compose -f
  .devcontainer/docker-compose.yml run --rm app` runs the same.
- Explore before you read, in this order, and stop at the first that answers: `codegraph explore
  "<symbols or question>"` for structure and call paths; `zg query "<what you are looking for>"` for
  where something lives when you do not know its name; `rtk grep` for an exact string; `Read` with a
  line range last. Never `cat` a file over two hundred lines without a range, and never read a file a
  subagent was asked to own.
- Every shell command goes through `rtk` (the hook rewrites it; do not fight the hook). `rtk test`,
  `rtk err`, `rtk diff` are the shapes for tests, builds and diffs.
- After a change to `src/`, `codegraph sync` and `zg index` keep the indexes current; the pre-commit
  hook runs both.
- `.codegraph/` and `.zvec-grep/` are indexes, ignored by git, rebuilt by `post-create.sh`.

## 10. Working as a subagent

The orchestrator fans a phase of `tasks/plan.md` out one slice or one document per subagent. If you are
one of them:

- Your inputs are this file, `docs/architecture.md`, your slice's section of `specs/03-features.md`,
  and the entities and flows for your slice in `specs/01-dynamodb-data-model.md`. Read those, then
  `codegraph explore` the slice, then start. Do not re-read the sibling repositories.
- Your scope is your slice's directory, its tests and its frontend: `frontend/src/test/fixtures/<slice>.ts`
  and the screen folders `frontend/CLAUDE.md`'s Navigation table gives your slice, with the
  `rules.ts` beside each screen. You do not edit `shared/`, another slice, a spec, `pyproject.toml` or
  `aws-cloud`. A change you need there goes in your report under "Needs from the orchestrator", with
  the smallest wording that would unblock you, and you build the rest around the assumption you
  state.
- Ponytail governs what you build. Before writing anything ask, in order: does it need to exist; is it
  already in `shared/` or a sibling slice's `service.py`; does the stdlib do it; does an approved
  dependency do it; can it be one function. Stop at the first rung that holds. No abstraction with one
  implementation, no configuration for a value that never changes, no scaffolding for a later phase.
- A deliberate simplification with a known ceiling is recorded in `specs/01-dynamodb-data-model.md`
  under "Deliberate simplifications and their ceilings" by the orchestrator; name it in your report,
  never in code.
- Do not stop to ask. Decide the way a careful colleague would, write the assumption down in the
  report, and finish. The only blocking question is one where every reading leads to materially
  different work, and even then finish everything that does not depend on it.
- Done means: `scripts/check.sh` green with its tail pasted; every public message asserted; every
  ceiling tested on both sides; no comments; no new dependency; the report in this shape:

  ```
  Built: <one line per behaviour>
  Skipped: <what, and when to add it>
  Assumed: <one line each>
  Needs from the orchestrator: <one line each, or "nothing">
  Check: <last lines of scripts/check.sh>
  ```
- After any correction from the orchestrator or the user, add the pattern to `tasks/lessons.md` in
  the same change, as "what happened, rule, check".

## 11. Frontend

`frontend/CLAUDE.md` owns the page: `screens/` following the URL, each with its pure rules in
`rules.ts`, over `api/`, the client typed from the generated spec, the six component rules of the
frontend standard, CSS Modules as the scoping mechanism, and the lint gate. This file stays Python and
infrastructure.
