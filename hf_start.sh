#!/usr/bin/env bash
set -euo pipefail
export PORT="${PORT:-7860}"
if [ -n "${RENDER_EXTERNAL_URL:-}" ]; then PUBLIC_URL="$RENDER_EXTERNAL_URL"
elif [ -n "${SPACE_HOST:-}" ]; then PUBLIC_URL="https://${SPACE_HOST}"
else PUBLIC_URL="http://localhost:${PORT}"; fi
export API_URL="$PUBLIC_URL" DEPLOY_URL="$PUBLIC_URL" CORS_ORIGINS="$PUBLIC_URL" TZ="${TZ:-Asia/Kolkata}"
echo "[start] reflex prod (unified) on :$PORT ($PUBLIC_URL)"
exec reflex run --env prod --backend-port "$PORT" --frontend-port "$PORT"
