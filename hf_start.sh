#!/usr/bin/env bash
# Startup for Hugging Face Spaces (Docker). HF exposes ONE port (7860); Reflex needs
# two (frontend 3000 + backend 8000), so Caddy reverse-proxies both behind :7860.
set -euo pipefail

# HF Spaces injects SPACE_HOST, e.g. "username-fantasy-sports.hf.space".
PUBLIC_URL="https://${SPACE_HOST:-localhost:7860}"
export API_URL="$PUBLIC_URL"
export DEPLOY_URL="$PUBLIC_URL"
export CORS_ORIGINS="$PUBLIC_URL"
export TZ="${TZ:-Asia/Kolkata}"

echo "[hf_start] public URL: $PUBLIC_URL"

# Build the compiled frontend now that the public backend URL is known (it gets baked
# into the frontend's websocket target).
echo "[hf_start] exporting frontend..."
reflex export --frontend-only --no-zip

# Backend (8000) + static frontend (3000); Caddy fronts both on 7860.
echo "[hf_start] starting reflex (backend 8000 / frontend 3000)..."
reflex run --env prod --backend-port 8000 --frontend-port 3000 &

echo "[hf_start] starting caddy on :7860..."
exec caddy run --config /app/Caddyfile --adapter caddyfile
