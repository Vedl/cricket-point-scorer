import os

import reflex as rx

# Backend URL handling:
#   * Reflex Cloud (reflex deploy) manages api_url/deploy_url itself → leave unset.
#   * Laptop tunnel/VPS → set API_URL (e.g. https://auction.example.com), DEPLOY_URL,
#     and CORS_ORIGINS (comma-separated) so the browser reaches the backend.
#   * Local dev → unset → Reflex's own localhost defaults apply.
_api_url = os.environ.get("API_URL")
_deploy_url = os.environ.get("DEPLOY_URL")
_cors = os.environ.get("CORS_ORIGINS")
# Websocket by default: verified (2026-07-04) that Render/Cloudflare pass the wss
# upgrade through to the app — the old "polling survives proxies" rationale dated
# from a bug in the static-serving ASGI wrapper (it didn't route websocket scopes),
# which was fixed in the same commit that switched to polling. Polling costs a full
# HTTP round-trip per event/delta, which on the 0.1-vCPU free instance was a big
# part of the deadline-hour lag. Set REFLEX_TRANSPORT=polling to fall back.
_transport = os.environ.get("REFLEX_TRANSPORT", "websocket")
if _transport not in ("websocket", "polling"):
    _transport = "websocket"

_kwargs = dict(
    app_name="fantasy_auction",
    transport=_transport,
    # Hide Reflex's "Built with Reflex" sticky badge. It renders position:fixed in the
    # bottom-right and overlaps the mobile bottom tab bar ("More"). Self-hosted prod
    # defaults this to True; the flag is the supported way to turn it off.
    show_built_with_reflex=False,
    # SQLite is unused — Firebase is the datastore (PLAN.md §6.6). Reflex still
    # wants a db_url for its internal bookkeeping; keep a throwaway local file.
    db_url="sqlite:///reflex_internal.db",
    # Theme configured here (not on rx.App, which is deprecated in 0.9).
    plugins=[
        rx.plugins.RadixThemesPlugin(
            theme=rx.theme(appearance="dark", accent_color="violet", gray_color="slate",
                           radius="large", scaling="100%"),
        ),
    ],
)
if _api_url:
    _kwargs["api_url"] = _api_url
if _deploy_url:
    _kwargs["deploy_url"] = _deploy_url
if _cors:
    _kwargs["cors_allowed_origins"] = [o.strip() for o in _cors.split(",") if o.strip()]

config = rx.Config(**_kwargs)
