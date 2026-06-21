"""Is a background loop's own client still connected?

This is the SINGLE chokepoint for the Reflex-internal APIs used to answer that:
  * the per-session token    -> ``state.router.session.client_token``
  * the live socket registry -> ``app.event_namespace._token_manager.token_to_socket``

Reflex 0.9.3 (pinned in requirements) removes a client's token from that map only
when its engine.io session actually CLOSES — a real disconnect / ping-timeout — and
NOT between the many HTTP requests of a single polling client: one persistent ``sid``
is reused across poll cycles, so ``EventNamespace.on_disconnect`` (which calls
``disconnect_token`` -> ``token_to_socket.pop(token)``) fires once per session
teardown, never per poll. Therefore:

  * token PRESENT  -> the client is still connected (or polling normally);
  * token ABSENT   -> the engine.io session has been torn down -> client gone.

NOTE on the path: ``_token_manager`` lives on the **EventNamespace**, not on the
``App``. ``App`` has no ``_token_manager`` attribute — the first version of this file
used ``app._token_manager`` and raised ``AttributeError`` on every call, which the
fail-open ``except`` swallowed, silently disabling the whole fix. To make that class
of mistake impossible to miss again, every call is classified ALIVE / DEAD /
FAILED_OPEN, the counts are tallied process-wide, and FAILED_OPEN is logged loudly
(rate-limited). If a Reflex upgrade moves this path, FAILED_OPEN will spike in the
logs instead of the fix going quietly dead. Keeping every framework internal in this
one file means such an upgrade only has to change here.
"""

from __future__ import annotations

import os
import threading
import time

import reflex as rx  # noqa: F401  (kept so this module fails fast if reflex is absent)

# Outcome of a single liveness evaluation.
ALIVE = "ALIVE"            # token present in the live socket map -> connected
DEAD = "DEAD"             # token resolved but absent from the map -> disconnected
FAILED_OPEN = "FAILED_OPEN"  # couldn't determine -> treated as ALIVE (fail open)

# Process-wide tally so a silent no-op can never recur unnoticed. Read it from a
# debug endpoint / REPL if you ever need to confirm the fix is live.
counts: dict[str, int] = {ALIVE: 0, DEAD: 0, FAILED_OPEN: 0}
_counts_lock = threading.Lock()

# FAILED_OPEN is logged loudly but rate-limited so a persistent internal breakage
# warns clearly without re-flooding the logs the way the original bug did.
_FAILOPEN_LOG_EVERY = 30.0  # seconds
_last_failopen_log = 0.0

# When set (LIVENESS_DEBUG=1) every outcome — including ALIVE — is printed. Off in
# production so the common ALIVE path stays silent and can't re-create a log flood;
# DEAD (rare: ~2 per orphan death) and FAILED_OPEN are always surfaced.
_DEBUG = os.environ.get("LIVENESS_DEBUG", "").strip().lower() in ("1", "true", "yes", "on")


def _log(msg: str) -> None:
    print(f"[liveness] {msg}", flush=True)


def _running_app():
    """The live ``rx.App`` instance the server is serving.

    Imported lazily: this module is imported (transitively) by
    ``fantasy_auction.fantasy_auction``, so a top-level import would be circular.
    At runtime the module is already loaded, so this is just a dict lookup.
    """
    from fantasy_auction.fantasy_auction import app

    return app


def _socket_map() -> dict:
    """Reflex 0.9.3 live token->socket registry (see module docstring for the path).

    Raises if the namespace isn't initialised or the internal path has moved — the
    caller turns any raise into a FAILED_OPEN so a live loop is never wrongly killed.
    """
    ns = _running_app().event_namespace
    if ns is None:
        raise RuntimeError("event_namespace not initialised yet")
    return ns._token_manager.token_to_socket


def _evaluate(state: rx.State) -> tuple[str, str]:
    """Classify the client behind ``state`` as ALIVE / DEAD / FAILED_OPEN.

    Returns ``(outcome, detail)`` and NEVER raises. ``detail`` is the token for
    ALIVE/DEAD, or a reason string for FAILED_OPEN.
    """
    try:
        token = state.router.session.client_token
    except Exception as exc:
        return FAILED_OPEN, f"token unresolved: {exc!r}"
    if not token:
        return FAILED_OPEN, "token empty"
    try:
        present = token in _socket_map()
    except Exception as exc:
        return FAILED_OPEN, f"socket map unreadable for {token!r}: {exc!r}"
    return (ALIVE, token) if present else (DEAD, token)


def client_connected(state: rx.State) -> bool:
    """Return True if ``state``'s own client still holds a live socket.

    FAIL OPEN: if the token can't be resolved or the framework map can't be read for
    ANY reason, report the client as ALIVE (return True) — a transient internal error
    must never kill a live loop; the worst case is an orphan lingers a little longer.
    Every call is counted, and FAILED_OPEN is logged loudly (rate-limited) so the fix
    can never silently become a no-op again.
    """
    outcome, detail = _evaluate(state)
    with _counts_lock:
        counts[outcome] += 1
        failopen_total = counts[FAILED_OPEN]

    if outcome == FAILED_OPEN:
        global _last_failopen_log
        now = time.monotonic()
        if now - _last_failopen_log >= _FAILOPEN_LOG_EVERY:
            _last_failopen_log = now
            _log(
                f"FAILED_OPEN ({detail}) — treating client as ALIVE, so loop "
                f"self-termination is DISABLED. FAILED_OPEN total={failopen_total}. "
                f"Check the Reflex token-map path; reflex is pinned to 0.9.3."
            )
        return True

    if outcome == DEAD:
        _log(f"DEAD token={detail!r} — client gone; loop will self-terminate.")
    elif _DEBUG:
        _log(f"ALIVE token={detail!r}")
    return outcome == ALIVE
