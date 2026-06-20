"""Is a background loop's own client still connected?

This is the SINGLE chokepoint for the Reflex-internal APIs used to answer that:
  * the per-session token       -> ``state.router.session.client_token``
  * the live socket registry    -> ``app._token_manager.token_to_socket``

Reflex 0.9.* (our pin) removes a client's token from that map only when its
engine.io session actually CLOSES — a real disconnect / ping-timeout — and NOT
between the many HTTP requests of a single polling client: one persistent ``sid``
is reused across poll cycles, so ``on_disconnect`` (which calls
``disconnect_token`` -> ``token_to_socket.pop(token)``) fires once per session
teardown, never per poll. Therefore:

  * token PRESENT  -> the client is still connected (or polling normally);
  * token ABSENT   -> the engine.io session has been torn down -> client gone.

Keeping every framework internal in this one file means a future Reflex upgrade
only has to touch here.
"""

from __future__ import annotations

import reflex as rx


def _running_app():
    """The live ``rx.App`` instance the server is serving.

    Imported lazily: this module is imported (transitively) by
    ``fantasy_auction.fantasy_auction``, so a top-level import would be circular.
    At runtime the module is already loaded, so this is just a dict lookup.
    """
    from fantasy_auction.fantasy_auction import app

    return app


def client_connected(state: rx.State) -> bool:
    """Return True if ``state``'s own client still holds a live socket.

    FAIL OPEN: if the token can't be resolved or the framework map can't be read
    for ANY reason (exception, renamed internal, not yet initialised), report the
    client as ALIVE. A transient internal error must never kill a live loop — the
    worst case is that an orphan lingers a little longer, never that a connected
    client's loop is wrongly torn down.
    """
    try:
        token = state.router.session.client_token
        if not token:
            return True  # token not resolvable yet → assume alive
        return token in _running_app()._token_manager.token_to_socket
    except Exception:
        return True
