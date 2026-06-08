"""Open-bidding glue over the room document, with deadline-driven windows.

Timeline relative to the admin's bidding deadline T:
  * before T-60m : open — bid on new players or raise.
  * T-60m .. T-30m : no new players — existing bids may be raised normally.
  * T-30m .. T : final window — existing bids may only be raised in +5M steps.
  * at T : all standing bids are awarded to the high bidders (scheduler).
  * no deadline set : bidding is FROZEN.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from season_engine.open_bidding import (
    BidError,
    active_bids,
    place_bid,
    resolve_expired,
)

from .config_layer import load_player_pool

MAX_SQUAD = 30


def _by(room):
    return {p["name"]: p for p in room.get("participants", [])}


def owned_names(room) -> set[str]:
    names = set()
    for p in room.get("participants", []):
        for e in p.get("squad", []):
            names.add(e["name"].lower())
    return names


def _pool(room) -> list[dict]:
    if room.get("player_pool"):
        return [{"name": p["name"], "role": p.get("role", ""), "team": p.get("team", "")}
                for p in room["player_pool"]]
    return [{"name": p.name, "role": p.role, "team": p.team}
            for p in load_player_pool(room.get("tournament_type", "T20 World Cup"))]


def available_players(room, *, search: str = "", limit: int = 60) -> list[dict]:
    owned = owned_names(room)
    s = search.strip().lower()
    out = []
    for p in _pool(room):
        if p["name"].lower() in owned:
            continue
        if s and s not in p["name"].lower() and s not in p["team"].lower():
            continue
        out.append(p)
        if len(out) >= limit:
            break
    return out


def _player(room, player_name) -> dict | None:
    for p in _pool(room):
        if p["name"].lower() == player_name.lower():
            return p
    return None


def bidding_deadline(room) -> datetime | None:
    iso = room.get("bidding_deadline")
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso)
        if dt.tzinfo is not None:
            dt = dt.astimezone().replace(tzinfo=None)
        return dt
    except (ValueError, TypeError):
        return None


def window_state(room, now: datetime) -> str:
    dl = bidding_deadline(room)
    if dl is None:
        return "frozen"
    if now >= dl:
        return "closed"
    if now >= dl - timedelta(minutes=30):
        return "raise_only"
    if now >= dl - timedelta(minutes=60):
        return "no_new"
    return "open"


def place(room, participant, player_name, amount, now: datetime) -> None:
    st = window_state(room, now)
    if st == "frozen":
        raise BidError("Bidding is frozen until the admin sets a deadline.")
    if st == "closed":
        raise BidError("Bidding has closed for this gameweek.")
    player = _player(room, player_name)
    if player is None:
        raise BidError(f"Unknown player {player_name!r}.")
    if player["name"].lower() in owned_names(room):
        raise BidError(f"{player_name} is already owned.")
    existing = any(k.lower() == player["name"].lower() for k in room.get("open_bids", {}))
    if st in ("no_new", "raise_only") and not existing:
        raise BidError("Bidding is closing — no new players, only raise existing bids.")
    dl = bidding_deadline(room)
    expiry = now + timedelta(hours=3)
    if dl and dl < expiry:
        expiry = dl
        
    place_bid(_by(room), room.setdefault("open_bids", {}), player, participant, amount,
              expiry.isoformat(), raise_only=(st == "raise_only"), max_squad=MAX_SQUAD)


def resolve_deadline(room, now: datetime) -> list[dict]:
    """Award all standing bids once the deadline passes (idempotent)."""
    dl = bidding_deadline(room)
    if dl is None or now < dl or room.get("bids_resolved"):
        return []
    awarded = resolve_expired(_by(room), room.setdefault("open_bids", {}), "9999-99-99", max_squad=MAX_SQUAD)
    room["bids_resolved"] = True
    if awarded:
        room.setdefault("transactions", []).extend(awarded)
    return awarded

def process_expired(room, now: datetime) -> list[dict]:
    """Award bids that have reached their 24h individual expiration."""
    awarded = resolve_expired(_by(room), room.setdefault("open_bids", {}), now.isoformat(), max_squad=MAX_SQUAD)
    if awarded:
        room.setdefault("transactions", []).extend(awarded)
    return awarded


def active(room) -> list[dict]:
    return active_bids(room.get("open_bids", {}))
