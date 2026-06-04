#!/usr/bin/env bash
# Host-agnostic startup (Hugging Face Spaces OR Render). Reflex 0.9 prod serves the
# frontend AND backend on ONE unified port.
set -euo pipefail

# Port: HF expects 7860; Render injects $PORT.
PORT="${PORT:-7860}"

# Public URL (baked into the frontend as the websocket target):
#   - Render sets RENDER_EXTERNAL_URL = full https URL
#   - HF Spaces sets SPACE_HOST = host only (served on :443)
if [ -n "${RENDER_EXTERNAL_URL:-}" ]; then
  PUBLIC_URL="$RENDER_EXTERNAL_URL"
elif [ -n "${SPACE_HOST:-}" ]; then
  PUBLIC_URL="https://${SPACE_HOST}"
else
  PUBLIC_URL="http://localhost:${PORT}"
fi
export API_URL="$PUBLIC_URL"
export DEPLOY_URL="$PUBLIC_URL"
export CORS_ORIGINS="$PUBLIC_URL"
export TZ="${TZ:-Asia/Kolkata}"

echo "[start] public URL: $PUBLIC_URL — unified Reflex on :$PORT"
exec reflex run --env prod --backend-port "$PORT" --frontend-port "$PORT"
