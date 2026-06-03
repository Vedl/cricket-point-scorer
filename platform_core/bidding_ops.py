"""Open-bidding glue over the room document (24h standing-bid market).

Available players = the event's full pool minus everyone's owned players. Imported
(post-Zoom-auction) squads are therefore excluded automatically. Bids live in
``room['open_bids']`` keyed by player name.
"""

from __future__ import annotations

from season_engine.open_bidding import (
    BidError,
    active_bids,
    place_bid,
    resolve_due,
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
    pool = load_player_pool(room.get("tournament_type", "T20 World Cup"))
    return [{"name": p.name, "role": p.role, "team": p.team} for p in pool]


def available_players(room, *, search: str = "", limit: int = 60) -> list[dict]:
    """Unowned players available for open bidding (optionally filtered)."""
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


def place(room, participant, player_name, amount, now, *, window=None) -> None:
    player = _player(room, player_name)
    if player is None:
        raise BidError(f"Unknown player {player_name!r}.")
    if player["name"].lower() in owned_names(room):
        raise BidError(f"{player_name} is already owned.")
    kwargs = {"max_squad": MAX_SQUAD}
    if window is not None:
        kwargs["window"] = window
    place_bid(_by(room), room.setdefault("open_bids", {}), player, participant, amount, now, **kwargs)


def resolve(room, now) -> list[dict]:
    awarded = resolve_due(_by(room), room.setdefault("open_bids", {}), now, max_squad=MAX_SQUAD)
    if awarded:
        room.setdefault("transactions", []).extend(awarded)
    return awarded


def active(room, now) -> list[dict]:
    return active_bids(room.get("open_bids", {}), now)
