#!/usr/bin/env bash
# Local preview against a scratch JSON datastore — NEVER touches prod Firebase.
set -euo pipefail
cd "$(dirname "$0")/.."
export FIREBASE_DATABASE_URL=""
export FIREBASE_SECRET=""
export FIREBASE_SECRET_KEY=""
export FIREBASE_API_KEY=""
export AUCTION_DATA_FILE="/tmp/claude_preview_auction.json"
export SCHEDULER_ENABLED="0"
export REFLEX_TRANSPORT="websocket"
FRONTEND_PORT="${PORT:-3100}"
BACKEND_PORT="${BACKEND_PORT:-8101}"
export API_URL="http://localhost:${BACKEND_PORT}"
exec .venv/bin/python -m reflex run \
  --frontend-port "$FRONTEND_PORT" --backend-port "$BACKEND_PORT"
