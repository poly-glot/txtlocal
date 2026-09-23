#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

export AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:-local}"
export AWS_ENDPOINT_URL_DYNAMODB="${AWS_ENDPOINT_URL_DYNAMODB:-http://localhost:8000}"
export AWS_REGION="${AWS_REGION:-eu-west-2}"
export AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:-local}"
export TABLE_NAME="${TABLE_NAME:-txtlocal-local}"

aws dynamodb delete-table --endpoint-url "$AWS_ENDPOINT_URL_DYNAMODB" --table-name "$TABLE_NAME" >/dev/null 2>&1 || true
until ! aws dynamodb describe-table --endpoint-url "$AWS_ENDPOINT_URL_DYNAMODB" --table-name "$TABLE_NAME" >/dev/null 2>&1; do
    sleep 1
done

scripts/local-table.sh
uv run python -m txtlocal.entrypoints.seed
echo "reset: $TABLE_NAME is empty and seeded"
