#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

step() {
    echo "check: $1"
    shift
    "$@"
}

if [ -z "${AWS_ENDPOINT_URL_DYNAMODB:-}" ] && scripts/local-table.sh >/dev/null 2>&1; then
    export AWS_ENDPOINT_URL_DYNAMODB=http://localhost:8000
    export AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:-local}"
    export AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:-local}"
    export AWS_REGION="${AWS_REGION:-eu-west-2}"
fi

if [ -z "${AWS_ENDPOINT_URL_DYNAMODB:-}" ]; then
    echo "check: WARNING DynamoDB Local is unreachable; every integration test will skip" >&2
fi

step "ruff format" uv run ruff format --check .
step "ruff check" uv run ruff check .
step "mypy" uv run mypy src
step "import-linter" uv run lint-imports
step "openapi" uv run python scripts/export_openapi.py --check
step "pytest" uv run pytest
echo "check: ok"
