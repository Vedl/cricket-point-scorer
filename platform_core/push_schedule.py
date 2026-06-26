"""Pure window math for the timed deadline push alerts.

No I/O — given a bidding deadline ``dl``, the current time ``now``, and the set of
already-fired dedup keys, ``due_alerts`` returns the (key, title, body) tuples that
should be sent right now. This is the only place the milestone timeline + copy live,
so it is trivially unit-testable (see tests/test_push_schedule.py).

Milestone moments are derived from the CANONICAL offsets in bidding_ops / season_ops
(never re-hardcoded here):

    A new_close   = dl − NEW_PLAYER_CUTOFF_MIN   (new-player bids close)
    B raise_only  = dl − RAISE_ONLY_MIN          (+5M-only window begins)
    C bid_close   = dl                            (bidding closes, bids award)
    D squad_lock  = dl + TRADING_LOCK_MIN         (trading closes, squads lock)

Windowed, jitter-tolerant firing for a milestone moment M:
    offset 60 ("1h before") → fires when  M-60 <= now < M-30
    offset 30 ("30m before")→ fires when  M-30 <= now < M
    offset 0  ("at moment") → fires when  M    <= now < M+10
A single missed minute inside a window just defers to the next tick; the bounded
windows guarantee a "1 hour left" can never arrive when only minutes remain.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from .bidding_ops import NEW_PLAYER_CUTOFF_MIN, RAISE_ONLY_MIN, parse_deadline
from .season_ops import TRADING_LOCK_MIN

# How long after the "moment" the at-moment alert may still fire (and, with the lock
# milestone, how long the whole schedule stays live before it can be pruned).
AT_WINDOW_MIN = 10

# (offset_minutes, title, body) per milestone. Offset 60 omitted for B by spec.
_SCHEDULE = {
    "new_close": [
        (60, "⏳ 1 hour left", "Bidding for new players closes in 1 hour."),
        (30, "⏳ 30 min left", "Bidding for new players closes in 30 minutes."),
        (0,  "🆕 New-player bids closed", "No new players now — you can only raise existing bids."),
    ],
    "raise_only": [
        (30, "⏳ 30 min to +5M-only", "In 30 minutes, bids can only be raised in +5M steps."),
        (0,  "5️⃣ +5M-only window", "Final window: existing bids can now only be raised in +5M steps."),
    ],
    "bid_close": [
        (60, "⏳ 1 hour left", "Bidding closes in 1 hour — standing bids award then."),
        (30, "⏳ 30 min left", "Bidding closes in 30 minutes — standing bids award then."),
        (0,  "🔨 Bidding closed", "Bidding is closed. Standing bids are being awarded."),
    ],
    "squad_lock": [
        (60, "⏳ 1 hour to squad lock", "Squads lock in 1 hour. Finish any trades and releases."),
        (30, "⏳ 30 min to squad lock", "Squads lock in 30 minutes. Finish any trades and releases."),
        (0,  "🔒 Squads locked", "Squads are locked for this gameweek. The next gameweek has started."),
    ],
}


def milestone_moments(dl: datetime) -> dict[str, datetime]:
    """The four milestone moments for a given bidding deadline."""
    return {
        "new_close": dl - timedelta(minutes=NEW_PLAYER_CUTOFF_MIN),
        "raise_only": dl - timedelta(minutes=RAISE_ONLY_MIN),
        "bid_close": dl,
        "squad_lock": dl + timedelta(minutes=TRADING_LOCK_MIN),
    }


def schedule_horizon(dl: datetime) -> datetime:
    """After this instant every alert window has closed and the schedule is prunable."""
    return dl + timedelta(minutes=TRADING_LOCK_MIN + AT_WINDOW_MIN)


def _in_window(moment: datetime, offset: int, now: datetime) -> bool:
    if offset == 0:
        return moment <= now < moment + timedelta(minutes=AT_WINDOW_MIN)
    # offset 30 → [M-30, M); offset 60 → [M-60, M-30)
    start = moment - timedelta(minutes=offset)
    end = moment - timedelta(minutes=offset - 30)
    return start <= now < end


def due_alerts(dl: datetime, now: datetime, fired: set[str] | None = None
               ) -> list[tuple[str, str, str]]:
    """Return [(dedup_key, title, body), ...] that should fire at ``now``.

    ``dedup_key`` is ``"{milestone}_{offset}"`` (e.g. "bid_close_30"). Keys already in
    ``fired`` are skipped. Order is stable (milestone order, then 60→30→0)."""
    fired = fired or set()
    moments = milestone_moments(dl)
    out: list[tuple[str, str, str]] = []
    for milestone, alerts in _SCHEDULE.items():
        moment = moments[milestone]
        for offset, title, body in alerts:
            key = f"{milestone}_{offset}"
            if key in fired:
                continue
            if _in_window(moment, offset, now):
                out.append((key, title, body))
    return out
