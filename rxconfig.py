import reflex as rx

config = rx.Config(
    app_name="fantasy_auction",
    # SQLite is unused — Firebase is the datastore (PLAN.md §6.6). Reflex still
    # wants a db_url for its internal bookkeeping; keep a throwaway local file.
    db_url="sqlite:///reflex_internal.db",
)
