# Production runbook

Everything in this repository runs locally today; the standing project instruction holds AWS
deployment until it is explicitly lifted. This file exists so that lift is a checklist, not a
rediscovery. It binds exactly as `CLAUDE.md` does and assumes it: read `specs/02-sms-gateway.md` for
the four `SMS_MODE` values and `docs/architecture.md` sections 2 and 5 for the Lambda map and the cost
ceiling before touching any of this.

Nothing here is a step to take today. It is the order to take them in, once told to.

## 0. Before any of this

- The `aws-cloud` pull request in `tasks/plan.md` section 3 is merged and deployed: the SQS/DLQ
  module inputs, SNS topics, End User Messaging configuration set and protect configuration, the
  self-sign-up Cognito pool, and `terraform/apps/txtlocal.tf`.
- `qa/01-routing.py`, `qa/02-negative.py`, `qa/03-idempotency.py` and `qa/04-load.py` all pass against
  the deployed stack's function URLs, not just `127.0.0.1`.
- `qa/05-cost.sh` passes: three alarms, no VPC, the shared table provisioned at 25/25, a retention on
  every log group.
- `SMS_MODE` has already been proven through `dryrun` (real API calls, `DryRun=true`, nothing sent)
  against the deployed stack, so this checklist starts from a codebase that has actually reached AWS
  End User Messaging once, not a codebase that has only ever run in `fake` mode.

## 1. The SMS production access support case

AWS accounts start in the SMS sandbox: sends succeed only to phone numbers verified on the account,
under a $1.00-a-month spend cap enforced by AWS itself (`specs/02-sms-gateway.md`, the `sandbox` row).
`SMS_MODE=sandbox` is this state, and it is where real-money verification happens before asking for
more.

- Open an AWS Support case, service "SNS text messaging" / "End User Messaging SMS", category
  "SMS and voice production access," for the account `aws-cloud` deploys into.
- State the use case plainly: transactional and marketing SMS on behalf of the platform's own
  customers, opt-out handled application-side (`messaging.policy`), expected volume from
  `docs/architecture.md` section 5's ceiling.
- This is a human review, not an API call. Budget days, not minutes, and do not schedule the
  remaining steps against a specific date until AWS confirms.

## 2. The spend quota raise and the protect configuration

Two fences `SendPolicy` does not implement, because AWS enforces them upstream of the application
entirely (`specs/02-sms-gateway.md`, the paragraph after the refusal table):

- **The account spend quota.** Starts at the minimum AWS grants. Raise it by a deliberate,
  by-hand quota request in the End User Messaging console, sized to a month of the trial cohort plus
  headroom, never left at a default large enough that a bug could spend past what this project can
  cover. Record the new figure in `docs/architecture.md` section 5 in the same change that raises it.
- **The protect configuration.** Confirm the country allow-list in the deployed protect configuration
  matches `SMS_ALLOWED_COUNTRIES` exactly. This is the fence that holds even if `SendPolicy` were
  bypassed by a bug; it is not a mirror of the app setting, it is the fence for when the mirror fails.

Both are `aws-cloud` changes (CLAUDE.md section 1: infrastructure and environment variables are a pull
request there, never here). Neither is reversible instantly — a lowered quota takes effect immediately,
a raised one may itself need AWS review.

## 3. Moving `SMS_MODE` to `live`

- `SMS_MODE` is an environment variable read once in `entrypoints/wiring.py` and nowhere else
  (`CLAUDE.md` section 1): the change is setting it in `aws-cloud`'s deploy configuration for the
  `api`, `send-worker` and `billing-renewals` functions (the three that touch `SmsGateway` per
  `docs/architecture.md` section 2), then redeploying. No code in this repository changes.
- Redeploy during low traffic. The first real `live` send is worth watching by hand: the
  `message_accepted` log line (`CLAUDE.md` section 6) and the `txtlocal-send-dlq` alarm are the two
  signals that something is wrong before a customer reports it.
- Roll back by setting `SMS_MODE` back to `sandbox` and redeploying. This is the same mechanism as
  going forward, which is why it is safe to attempt `live` during a low-traffic window rather than
  needing a separate rollback plan.

## 4. The Stripe sandbox and the live keys

- There is no fake payment gateway: every stage talks to Stripe, and until this step it is a Stripe
  sandbox of its own, so no other app's events reach the endpoint. `STRIPE_SECRET_KEY` and
  `STRIPE_WEBHOOK_SECRET` are read once in `wiring.py`; `aws-cloud` fills them from the
  `TXTLOCAL_STRIPE_SECRET_KEY` and `TXTLOCAL_STRIPE_WEBHOOK_SECRET` repository secrets and refuses to
  plan without them. An empty webhook secret refuses every event rather than trusting an HMAC anyone
  could compute.
- The deployed endpoint is the `stripe-webhook` function URL (`url = "public"`, not a CloudFront
  path), listening for `checkout.session.completed`, `payment_intent.succeeded` and
  `setup_intent.succeeded`; its signing secret is `TXTLOCAL_STRIPE_WEBHOOK_SECRET`.
- On a laptop the sandbox key goes in `.env` as `STRIPE_SECRET_KEY`. `scripts/dev.sh` then starts
  `stripe listen` in the dev container, forwarding the three events to the `/api/stripe-webhook`
  route `wiring.py` mounts only beside DynamoDB Local, and hands the API the `whsec_` the listener
  prints; its log is `.local/stripe-listen.log`. `STRIPE_WEBHOOK_SECRET` in `.env` is used only when
  the container has no Stripe CLI, for a listener run on the host.
- Going live means setting both secrets to the live-mode values, the same mechanism as any other
  environment variable here. Create the live-mode webhook endpoint in the Stripe dashboard, pointed
  at the same function URL with the same three events, before flipping the key, so the first live
  event has somewhere to land; `entrypoints/stripe_webhook.py` answers 200 for every terminal
  outcome so Stripe stops redelivering (`CLAUDE.md` section 4).
- A stored webhook signing secret is HMAC input on every delivery and cannot be hashed at rest
  (`CLAUDE.md` section 1); treat it exactly as the Stripe secret key itself, not as a password.
- Confirm with one real low-value top-up before announcing anything: `billing.service`'s conditional
  write settles the ledger row and the balance in the same transaction, but that invariant is worth
  seeing once against the real Stripe account rather than trusting the sandbox run alone.

## 5. After all four

Update `docs/architecture.md` section 5 with the real, observed first month's bill next to the
estimate, and record the date `SMS_MODE` reached `live` in this file's own history — a runbook that
does not say when it was last actually used is a runbook nobody trusts the next time.
