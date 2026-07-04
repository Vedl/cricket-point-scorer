#!/usr/bin/env bash
set -euo pipefail
export PORT="${PORT:-7860}"
if [ -n "${RENDER_EXTERNAL_URL:-}" ]; then PUBLIC_URL="$RENDER_EXTERNAL_URL"
elif [ -n "${SPACE_HOST:-}" ]; then PUBLIC_URL="https://${SPACE_HOST}"
else PUBLIC_URL="http://localhost:${PORT}"; fi
# Transport: websocket. Verified 2026-07-04 — Cloudflare/Render pass the wss
# upgrade to the app (probing /_event?transport=websocket reaches granian, which
# answered 400 "Invalid transport" purely because the server was polling-only).
# The 2026-06-09 "external users can't load" bug was the static-serving ASGI
# wrapper not routing websocket scopes, fixed in the same commit that introduced
# polling; polling was the workaround, not the fix. Polling costs a full HTTP
# round-trip per event/delta — on the 0.1-vCPU instance that is the deadline-hour
# lag. Emergency fallback: set REFLEX_TRANSPORT=polling in the Render env.
export API_URL="$PUBLIC_URL" DEPLOY_URL="$PUBLIC_URL" CORS_ORIGINS="$PUBLIC_URL" \
       REFLEX_TRANSPORT="${REFLEX_TRANSPORT:-websocket}" TZ="${TZ:-Asia/Kolkata}"

# Sync baked frontend env (build-time URL/transport) with runtime Render URL.
python3 - <<'PY'
import glob, json, os, re
url = os.environ.get("API_URL", "").rstrip("/")
transport = os.environ.get("REFLEX_TRANSPORT", "websocket")
if not url:
    raise SystemExit(0)
env = {
    "PING": f"{url}/ping",
    "EVENT": f"{url}/_event",
    "UPLOAD": f"{url}/_upload",
    "AUTH_CODESPACE": f"{url}/auth-codespace",
    "HEALTH": f"{url}/_health",
    "ALL_ROUTES": f"{url}/_all_routes",
    "TRANSPORT": transport,
    "TEST_MODE": False,
}
for path in [".web/env.json", *glob.glob(".web/build/client/assets/reflex-env-*.js")]:
    if not os.path.isfile(path):
        continue
    if path.endswith(".json"):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(env, f)
    else:
        with open(path, encoding="utf-8") as f:
            txt = f.read()
        event = env["EVENT"].replace("http://", "ws://").replace("https://", "wss://")
        patched = re.sub(
            r"var e=\{[^}]+\};export\{e as t\};",
            "var e=" + json.dumps({**env, "EVENT": event}, separators=(",", ":")) + ";export{e as t};",
            txt,
            count=1,
        )
        if patched != txt:
            with open(path, "w", encoding="utf-8") as f:
                f.write(patched)
PY

# auction_data.json is excluded from the Docker image (.dockerignore). On a cold
# Render start the first websocket hydrate would otherwise block the asyncio loop
# on a synchronous Firebase download (~1 MB), starving the socket heartbeat and
# leaving users stuck on "connecting…". Warm the in-memory cache here, before the
# server accepts traffic, so event handlers never pay that cost on the hot path.
python - <<'PY'
import os, time
os.environ.setdefault("TZ", os.environ.get("APP_TZ", "Asia/Kolkata"))
from platform_core.firebase_store import warm_cache
t = time.time()
warm_cache()
print(f"[start] datastore cache warmed in {time.time() - t:.1f}s")
PY

echo "[start] backend-only (serves prebuilt static frontend) on :$PORT ($PUBLIC_URL, transport=$REFLEX_TRANSPORT)"
exec reflex run --env prod --backend-only --backend-port "$PORT"
