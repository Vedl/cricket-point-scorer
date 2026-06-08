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
# Polling survives reverse proxies (Render/Cloudflare) that drop WebSocket Upgrade
# headers; override with REFLEX_TRANSPORT=websocket for local dev if preferred.
_transport = os.environ.get("REFLEX_TRANSPORT", "polling")
if _transport not in ("websocket", "polling"):
    _transport = "polling"

_kwargs = dict(
    app_name="fantasy_auction",
    transport=_transport,
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
