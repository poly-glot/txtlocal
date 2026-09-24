#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -f .env ]; then
    set -a
    . ./.env
    set +a
fi

export AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:-local}"
export AWS_ENDPOINT_URL_DYNAMODB="${AWS_ENDPOINT_URL_DYNAMODB:-http://localhost:8000}"
export AWS_REGION="${AWS_REGION:-eu-west-2}"
export AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:-local}"
export BUS=local
export COGNITO_CLIENT_ID="${COGNITO_CLIENT_ID:-local}"
export DEV_IDP_USERS="${DEV_IDP_USERS:-demo@txtlocal.local,sub@txtlocal.local}"
export PUBLIC_BASE_URL="${PUBLIC_BASE_URL:-http://localhost:3000}"
export SMS_ALLOWED_COUNTRIES="${SMS_ALLOWED_COUNTRIES:-GB,US,CA}"
export SMS_MODE=fake
export TABLE_NAME="${TABLE_NAME:-txtlocal-local}"
export UNSUBSCRIBE_SECRET="${UNSUBSCRIBE_SECRET:-local-unsubscribe-secret}"
export VITE_COGNITO_CLIENT_ID="${COGNITO_CLIENT_ID}"
export VITE_COGNITO_DOMAIN="${PUBLIC_BASE_URL}/api/dev-idp"

command -v uv >/dev/null 2>&1 || { echo "uv not found: open this repo in the dev container" >&2; exit 1; }

PIDS=()
trap 'kill "${PIDS[@]}" 2>/dev/null' EXIT

scripts/local-table.sh
scripts/seed.sh

mkdir -p .local
export API_LOG_FILE="${API_LOG_FILE:-$PWD/.local/api.jsonl}"
export MEDIA_DIR="${MEDIA_DIR:-$PWD/.local/media}"
export HOST=0.0.0.0

if [ -n "${STRIPE_SECRET_KEY:-}" ] && command -v stripe >/dev/null; then
    stripe listen --api-key "$STRIPE_SECRET_KEY" \
        --events checkout.session.completed,payment_intent.succeeded,setup_intent.succeeded \
        --forward-to http://localhost:9000/api/stripe-webhook > .local/stripe-listen.log 2>&1 &
    PIDS+=($!)

    for _ in $(seq 1 30); do
        grep -q 'Ready!' .local/stripe-listen.log && break
        sleep 1
    done

    listen_secret="$(grep -o -m1 'whsec_[A-Za-z0-9]*' .local/stripe-listen.log || true)"
    if [ -n "$listen_secret" ]; then
        export STRIPE_WEBHOOK_SECRET="$listen_secret"
        echo "stripe: forwarding sandbox webhooks to /api/stripe-webhook, log in .local/stripe-listen.log"
    else
        echo "stripe listen did not become ready; see .local/stripe-listen.log" >&2
    fi
fi

uv run python -m txtlocal.entrypoints.dev_server > >(tee -a "$API_LOG_FILE") 2>&1 &
PIDS+=($!)

uv run python -m txtlocal.entrypoints.scheduler >> "$API_LOG_FILE" 2>&1 &
PIDS+=($!)

if [ -f frontend/package.json ]; then
    pnpm --dir frontend dev --host 0.0.0.0 --port 3000 &
    PIDS+=($!)
    echo "ready: http://localhost:3000"
else
    echo "ready: http://localhost:9000/docs (frontend/ not present yet)"
fi
wait
