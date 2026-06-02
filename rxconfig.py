import os

import reflex as rx

# In production the browser must reach the backend at a public URL. Set API_URL
# (e.g. https://auction.example.com) for a VPS; defaults to localhost for dev.
_api_url = os.environ.get("API_URL", "http://localhost:8000")

config = rx.Config(
    app_name="fantasy_auction",
    api_url=_api_url,
    # SQLite is unused — Firebase is the datastore (PLAN.md §6.6). Reflex still
    # wants a db_url for its internal bookkeeping; keep a throwaway local file.
    db_url="sqlite:///reflex_internal.db",
    # Theme configured here (not on rx.App, which is deprecated in 0.9).
    plugins=[
        rx.plugins.RadixThemesPlugin(
            theme=rx.theme(appearance="dark", accent_color="blue", radius="large"),
        ),
    ],
)
