# Cost report

The dollar estimate lives in `docs/architecture.md` section 5: about $1.40 a month at the ceiling, on
top of the shared platform's existing $0.35, with SMS spend in `sandbox` mode as the only number that
can move. This file does not repeat that table. It is the structural arithmetic behind
`qa/05-cost.sh`'s assertions — the AWS-CLI-verifiable facts that make the dollar estimate true, the way
`shorten/qa/COST.md` documents its own script.

## Why each assertion is there

**The shared table is provisioned at 25/25, not on-demand.** `docs/architecture.md`'s $0 line for
DynamoDB assumes txtlocal's reads and writes fit inside the platform's `aws-cloud` table, whose 25 read
and 25 write units are shared three ways with `donation` and `shorten`. On-demand billing would still
work functionally, but it bills per request rather than sitting inside an allowance already paid for at
zero — `05-cost.sh` asserts `PROVISIONED`, not merely "works."

**Every function is outside a VPC.** A VPC-attached Lambda needs a NAT gateway to reach anything
outside it, and a NAT gateway is about $32 a month before a single byte crosses it — more than the
entire rest of this budget combined. txtlocal's eleven functions (`docs/architecture.md` section 2)
only ever need the table, SQS, SNS, Stripe, Cognito and SMS, none of which need a VPC to reach.

**Every function's log group has an explicit retention.** `docs/architecture.md`'s $0 line for Logs
assumes usage stays inside the 5 GB-stored free tier. A log group with no retention policy keeps every
line forever; eleven functions logging one JSON line per request will cross 5 GB eventually, quietly,
with no alarm watching storage (CLAUDE.md section 6: "no custom metrics"). This repo does not yet write
down a specific number of days anywhere — see [open question 4](README.md#open-questions) — so
`05-cost.sh` only asserts that a retention exists, not which one.

**Exactly three alarms, by name.** CLAUDE.md section 1: "the alarm budget is three and all three are in
use," because the platform's ten free alarms are already spent (`aws-cloud-platform` memory: `donation`
alone uses them). `docs/architecture.md` section 2 names the three: `txtlocal-api-errors` on
`AWS/Lambda Errors`, `txtlocal-send-dlq` on the send dead-letter queue's
`ApproximateNumberOfMessagesVisible`, and `txtlocal-rollup-failed` over 24 hours with missing data
breaching. A fourth alarm, from any source, bills about $0.10 a month it was never budgeted for.

## What would actually move the bill

Everything above is $0 to $0.35 whether txtlocal sends one message a month or ten thousand, because it
all sits inside always-free allowances shared with two other apps. The one line that scales with real
usage is SMS itself, which is why `docs/architecture.md` keeps `sandbox` mode's spend quota low and
`live` mode raises it deliberately, by hand, per the production runbook in `docs/runbook.md` — not by a
Terraform default anyone could raise by accident.
