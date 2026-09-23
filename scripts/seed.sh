#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

if uv run python -c "import txtlocal.entrypoints.seed" >/dev/null 2>&1; then
    uv run python -m txtlocal.entrypoints.seed
else
    echo "seed: txtlocal.entrypoints.seed arrives with the identity slice; nothing seeded"
fi
