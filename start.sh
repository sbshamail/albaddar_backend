#!/usr/bin/env bash
# Started by PM2 (see ecosystem.config.js) — supervises this one process,
# which uvicorn itself forks into $UVICORN_WORKERS worker processes.
set -euo pipefail
cd "$(dirname "$0")"

WORKERS="${UVICORN_WORKERS:-4}"
PORT="${PORT:-8001}"

exec uv run -- uvicorn src.main:app --host 0.0.0.0 --port "$PORT" --workers "$WORKERS"
