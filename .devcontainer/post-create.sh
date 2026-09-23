#!/usr/bin/env bash
set -euo pipefail

sudo chown vscode:vscode /home/vscode/.venv frontend/node_modules 2>/dev/null || true
git config --global --add safe.directory /workspaces/txtlocal
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    git config core.hooksPath .githooks
fi
[ -f .env ] || cp .env.example .env

uv sync
if [ -f frontend/package.json ]; then
    pnpm --dir frontend install --frozen-lockfile || pnpm --dir frontend install
fi

npm install -g @colbymchenry/codegraph @zvec/zvec-grep
rtk init -g || echo "rtk init failed; run: rtk init -g"
codegraph init -y || echo "codegraph init failed; run: codegraph init -y"
zg index --embedding local/potion-code-16m-v2 || echo "zg index skipped (model download); run: zg index --embedding local/potion-code-16m-v2"

scripts/local-table.sh

echo "DynamoDB Local is at $AWS_ENDPOINT_URL_DYNAMODB; run: bash scripts/check.sh"
echo "API:      uv run uvicorn txtlocal.entrypoints.api:app --host 0.0.0.0 --port 9000"
echo "Frontend: pnpm --dir frontend dev"
echo "Both:     scripts/dev.sh"
