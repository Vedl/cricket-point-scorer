"""Open-bidding glue over the room document, with deadline-driven windows.

Timeline relative to the admin's bidding deadline T:
  * before T-60m : open — bid on new players or raise.
  * T-60m .. T-30m : no new players — existing bids may be raised normally.
  * T-30m .. T : final window — existing bids may only be raised in +5M steps.
  * at T : all standing bids are awarded to the high bidders (scheduler).
  * no deadline set : bidding is FROZEN.

Independently of that, a leading bid also wins the player once it has stood
unchallenged for the room's *bid hold* window (see ``bid_hold_hours``): 12 hours
until the GW1 deadline, 24 hours after it, both admin-adjustable. Any new high bid
restarts that clock, and the window is always clipped to the bidding deadline.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from season_engine.open_bidding import (
    BidError,
    active_bids,
    place_bid,
    resolve_expired,
)

from .config_layer import load_player_pool, room_player_pool

MAX_SQUAD = 30

# How long a leading bid must stand unchallenged before the player is awarded.
# Faster before the season starts (the opening auction needs to clear quickly),
# steadier once gameweeks are running. Both are admin-overridable per room via
# ``pre_gw1_bid_hold_hours`` / ``bid_hold_hours``.
DEFAULT_PRE_GW1_BID_HOLD_HOURS = 12
DEFAULT_BID_HOLD_HOURS = 24
MIN_BID_HOLD_HOURS = 1
MAX_BID_HOLD_HOURS = 168  # a week

# Canonical window offsets relative to the bidding deadline T (single source of truth;
# referenced by window_state below and by the deadline push scheduler).
NEW_PLAYER_CUTOFF_MIN = 60   # before T-60m you may bid on new players; after, raise-only
RAISE_ONLY_MIN = 30          # T-30m..T: existing bids may only be raised in +5M steps


def parse_deadline(iso) -> datetime | None:
    """Parse a stored ISO deadline string to a naive-local datetime (or None)."""
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso)
        if dt.tzinfo is not None:
            dt = dt.astimezone().replace(tzinfo=None)
        return dt
    except (ValueError, TypeError):
        return None


def _by(room):
    return {p["name"]: p for p in room.get("participants", [])}


def owned_names(room) -> set[str]:
    names = set()
    for p in room.get("participants", []):
        for e in p.get("squad", []):
            names.add(e["name"].lower())
    return names


# The bundled-pool view (~1300 small dicts for the FIFA pool) is immutable for the
# process lifetime, but it was rebuilt on EVERY available_players call — several
# times a second across the per-client live loops. Build it once per tournament.
# Callers treat the dicts as read-only (place_bid/awards copy fields into new
# dicts); rooms with a custom uploaded pool still rebuild per call since that
# pool lives in the (mutable) room document.
_BUILTIN_POOL_VIEW: dict[str, list[dict]] = {}


def _pool(room) -> list[dict]:
    # Fast path: the overwhelmingly common case is a room on its tournament's
    # bundled pool with nothing added, and this runs in every client's live loop.
    if not room.get("player_pool") and not room.get("extra_players"):
        tt = room.get("tournament_type", "T20 World Cup")
        view = _BUILTIN_POOL_VIEW.get(tt)
        if view is None:
            view = [{"name": p.name, "role": p.role, "team": p.team}
                    for p in load_player_pool(tt)]
            _BUILTIN_POOL_VIEW[tt] = view
        return view
    return [{"name": p.name, "role": p.role, "team": p.team}
            for p in room_player_pool(room)]


def available_players(room, *, search: str = "", country: str = "", role: str = "",
                      limit: int = 60, include_knocked_out: bool = False) -> list[dict]:
    """Unowned pool players, accent-insensitively matched against ``search`` and
    optionally filtered by nation + position. Players from knocked-out nations
    are hidden (they can't be bid on) unless ``include_knocked_out``."""
    from .textutil import fold
    owned = owned_names(room)
    ko = set() if include_knocked_out else set(room.get("knocked_out_countries", []) or [])
    s = fold(search)
    out = []
    for p in _pool(room):
        if p["name"].lower() in owned:
            continue
        if p.get("team") in ko:
            continue
        if country and p.get("team") != country:
            continue
        if role and p.get("role") != role:
            continue
        if s and s not in fold(p["name"]) and s not in fold(p["team"]):
            continue
        out.append(p)
        if len(out) >= limit:
            break
    return out


def _player(room, player_name) -> dict | None:
    from .textutil import fold
    want = fold(player_name)
    for p in _pool(room):
        if fold(p["name"]) == want:
            return p
    return None


def bidding_deadline(room) -> datetime | None:
    return parse_deadline(room.get("bidding_deadline"))


def window_state(room, now: datetime) -> str:
    dl = bidding_deadline(room)
    if dl is None:
        return "frozen"
    if now >= dl:
        return "closed"
    if now >= dl - timedelta(minutes=RAISE_ONLY_MIN):
        return "raise_only"
    if now >= dl - timedelta(minutes=NEW_PLAYER_CUTOFF_MIN):
        return "no_new"
    return "open"


def gw1_deadline_passed(room, now: datetime) -> bool:
    """Has the room reached its gameweek 1 deadline?

    True once GW1's squads are locked (the deadline fired), or once its stored
    deadline is in the past, or if the room is already past gameweek 1.
    """
    if "1" in (room.get("gameweek_squads") or {}):
        return True
    dl = parse_deadline((room.get("gameweek_deadlines") or {}).get("1"))
    if dl is not None:
        return now >= dl
    return int(room.get("current_gameweek", 0) or 0) > 1


def _clamp_hold(value, default: int) -> int:
    try:
        hours = int(value)
    except (TypeError, ValueError):
        return default
    if hours <= 0:
        return default
    return max(MIN_BID_HOLD_HOURS, min(MAX_BID_HOLD_HOURS, hours))


def bid_hold_hours(room, now: datetime) -> int:
    """Hours a leading bid must stand before the player is awarded to that bidder."""
    if gw1_deadline_passed(room, now):
        return _clamp_hold(room.get("bid_hold_hours"), DEFAULT_BID_HOLD_HOURS)
    return _clamp_hold(room.get("pre_gw1_bid_hold_hours"), DEFAULT_PRE_GW1_BID_HOLD_HOURS)


def set_bid_hold_hours(room, hours, *, pre_gw1: bool = False) -> int:
    """Admin sets the hold window (returns the stored value). Raises on nonsense."""
    try:
        value = int(hours)
    except (TypeError, ValueError):
        raise BidError("Enter a whole number of hours.")
    if not MIN_BID_HOLD_HOURS <= value <= MAX_BID_HOLD_HOURS:
        raise BidError(f"Hours must be between {MIN_BID_HOLD_HOURS} and {MAX_BID_HOLD_HOURS}.")
    room["pre_gw1_bid_hold_hours" if pre_gw1 else "bid_hold_hours"] = value
    return value


def place(room, participant, player_name, amount, now: datetime) -> None:
    st = window_state(room, now)
    if st == "frozen":
        raise BidError("Bidding is frozen until the admin sets a deadline.")
    if st == "closed":
        raise BidError("Bidding has closed for this gameweek.")
    if _by(room).get(participant, {}).get("is_eliminated"):
        raise BidError("You've been eliminated from the tournament — you can no longer bid.")
    player = _player(room, player_name)
    if player is None:
        raise BidError(f"Unknown player {player_name!r}.")
    if player["name"].lower() in owned_names(room):
        raise BidError(f"{player_name} is already owned.")
    if player.get("team") in set(room.get("knocked_out_countries", []) or []):
        raise BidError(f"{player.get('team')} is knocked out of the tournament — "
                       "their players can't be bid on.")
    existing = any(k.lower() == player["name"].lower() for k in room.get("open_bids", {}))
    if st in ("no_new", "raise_only") and not existing:
        raise BidError("Bidding is closing — no new players, only raise existing bids.")
    dl = bidding_deadline(room)
    expiry = now + timedelta(hours=bid_hold_hours(room, now))
    if dl and dl < expiry:
        expiry = dl

    place_bid(_by(room), room.setdefault("open_bids", {}), player, participant, amount,
              expiry.isoformat(), raise_only=(st == "raise_only"), max_squad=MAX_SQUAD)


def resolve_deadline(room, now: datetime) -> list[dict]:
    """Award all standing bids once the deadline passes (idempotent)."""
    dl = bidding_deadline(room)
    if dl is None or now < dl or room.get("bids_resolved"):
        return []
    # "9999-99-99" only means "every bid has expired" to resolve_expired. It must not
    # stay on the records: the announcements feed sorts newest-first by ts, so a
    # sentinel date pins those signings above every later event forever.
    awarded = resolve_expired(_by(room), room.setdefault("open_bids", {}), "9999-99-99", max_squad=MAX_SQUAD)
    for tx in awarded:
        tx["ts"] = now.isoformat()
    room["bids_resolved"] = True
    if awarded:
        room.setdefault("transactions", []).extend(awarded)
    return awarded

def process_expired(room, now: datetime) -> list[dict]:
    """Award bids that have stood for the room's full bid-hold window."""
    awarded = resolve_expired(_by(room), room.setdefault("open_bids", {}), now.isoformat(), max_squad=MAX_SQUAD)
    if awarded:
        room.setdefault("transactions", []).extend(awarded)
    return awarded


def active(room) -> list[dict]:
    return active_bids(room.get("open_bids", {}))
