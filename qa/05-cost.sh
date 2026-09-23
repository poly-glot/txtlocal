#!/usr/bin/env bash
set -euo pipefail

. "$(cd "$(dirname "$0")" && pwd)/lib.sh"

USAGE="usage: qa/05-cost.sh [--account <id>] [--table aws-cloud] [--functions \"txtlocal-api ...\"]

Executes the cost checklist against the deployed account. Every item is an AWS call with an
assertion, not a printed reminder, in the shape of the shorten repo's own qa/07-cost.sh. The written
report is qa/COST.md.

NOT YET RUN: txtlocal has no aws-cloud pull request and nothing deployed (see
tasks/plan.md section 3 and the project's standing AWS hold). This script is written and its argument
handling exercised; its AWS calls have not."

ALARM_COUNT=3
ALARM_PREFIX="txtlocal-"
FREE_CAPACITY_UNITS=25

while [ $# -gt 0 ]; do
    case "$1" in
        --account) ACCOUNT="$2"; shift 2 ;;
        --functions) FUNCTIONS="$2"; shift 2 ;;
        --table) TABLE="$2"; shift 2 ;;
        -h|--help) printf '%s\n' "$USAGE"; exit 0 ;;
        *) printf '%s\n' "$USAGE" >&2; die "unknown argument $1" ;;
    esac
done

require_command aws
discover_account

billing=$(aws dynamodb describe-table --table-name "$TABLE" \
    --query 'Table.BillingModeSummary.BillingMode || `PROVISIONED`' --output text)
assert_eq "PROVISIONED" "$billing" "the shared table is provisioned, not on-demand"

read_units=$(aws dynamodb describe-table --table-name "$TABLE" \
    --query 'sum([Table.ProvisionedThroughput.ReadCapacityUnits, sum(Table.GlobalSecondaryIndexes[].ProvisionedThroughput.ReadCapacityUnits)])' \
    --output text)
write_units=$(aws dynamodb describe-table --table-name "$TABLE" \
    --query 'sum([Table.ProvisionedThroughput.WriteCapacityUnits, sum(Table.GlobalSecondaryIndexes[].ProvisionedThroughput.WriteCapacityUnits)])' \
    --output text)
assert_eq "$FREE_CAPACITY_UNITS" "$read_units" "read capacity across the table and its indexes is the free $FREE_CAPACITY_UNITS units, shared with donation and shorten"
assert_eq "$FREE_CAPACITY_UNITS" "$write_units" "write capacity across the table and its indexes is the free $FREE_CAPACITY_UNITS units, shared with donation and shorten"

for function_name in $FUNCTIONS; do
    vpc=$(aws lambda get-function-configuration --function-name "$function_name" \
        --query 'VpcConfig.VpcId || `none`' --output text)
    assert_eq "none" "$vpc" "$function_name runs outside a VPC"

    retention=$(aws logs describe-log-groups --log-group-name-prefix "/aws/lambda/$function_name" \
        --query 'logGroups[0].retentionInDays || `NEVER`' --output text)
    if [ "$retention" = "NEVER" ] || [ "$retention" = "None" ]; then
        fail "$function_name's log group has an explicit retention, not 'never expire'"
    else
        pass "$function_name's log group expires after $retention days"
    fi
done

alarm_count=$(aws cloudwatch describe-alarms --alarm-name-prefix "$ALARM_PREFIX" \
    --query 'length(MetricAlarms)' --output text)
assert_eq "$ALARM_COUNT" "$alarm_count" "txtlocal owns exactly $ALARM_COUNT CloudWatch alarms, the number docs/architecture.md budgets"

for alarm_name in "${ALARM_PREFIX}api-errors" "${ALARM_PREFIX}send-dlq" "${ALARM_PREFIX}rollup-failed"; do
    exists=$(aws cloudwatch describe-alarms --alarm-names "$alarm_name" \
        --query 'length(MetricAlarms)' --output text)
    assert_eq "1" "$exists" "$alarm_name exists, matching docs/architecture.md section 2"
done

finish
