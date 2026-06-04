#!/usr/bin/env bash
set -euo pipefail
export PORT="${PORT:-7860}"
if [ -n "${RENDER_EXTERNAL_URL:-}" ]; then PUBLIC_URL="$RENDER_EXTERNAL_URL"
elif [ -n "${SPACE_HOST:-}" ]; then PUBLIC_URL="https://${SPACE_HOST}"
else PUBLIC_URL="http://localhost:${PORT}"; fi
export API_URL="$PUBLIC_URL" DEPLOY_URL="$PUBLIC_URL" CORS_ORIGINS="$PUBLIC_URL" TZ="${TZ:-Asia/Kolkata}"
echo "[start] backend-only :8000 + caddy static on :$PORT ($PUBLIC_URL)"
reflex run --env prod --backend-only --backend-port 8000 &
exec /usr/local/bin/caddy run --config /app/Caddyfile --adapter caddyfile
