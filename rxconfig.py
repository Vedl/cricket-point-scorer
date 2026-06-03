import os

import reflex as rx

# In production the browser must reach the backend at a public URL. Set API_URL
# (e.g. https://auction.example.com) for a VPS/tunnel; defaults to localhost for dev.
# DEPLOY_URL = public frontend origin; CORS_ORIGINS = comma-separated allowed origins.
_api_url = os.environ.get("API_URL", "http://localhost:8000")
_deploy_url = os.environ.get("DEPLOY_URL")
_cors = os.environ.get("CORS_ORIGINS")

_kwargs = dict(
    app_name="fantasy_auction",
    api_url=_api_url,
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
if _deploy_url:
    _kwargs["deploy_url"] = _deploy_url
if _cors:
    _kwargs["cors_allowed_origins"] = [o.strip() for o in _cors.split(",") if o.strip()]

config = rx.Config(**_kwargs)
