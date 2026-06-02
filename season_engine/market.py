"""Post-auction market — releases + sealed-bid open bidding on available players.

Pure functions over room-shaped participant dicts. Mirrors the legacy "Open
Bidding" tab: players that are unsold or released can be bid on; the highest valid
sealed bid wins (budget + squad enforced).
"""

from __future__ import annotations

from typing import Optional


class MarketError(Exception):
    """A market action was rejected (message is user-facing)."""


def _entry(participant: dict, player_name: str) -> Optional[dict]:
    return next(
        (e for e in participant.get("squad", []) if e["name"].lower() == player_name.lower()),
        None,
    )


def release_player(participant: dict, player_name: str, *, refund: bool = False) -> dict:
    """Drop a player from a squad back to the pool. Optionally refund the buy price.

    Returns a record of the released player (so the caller can add to the
    available/unsold pool).
    """
    e = _entry(participant, player_name)
    if e is None:
        raise MarketError(f"{participant['name']} doesn't own {player_name}.")
    participant["squad"].remove(e)
    if refund:
        participant["budget"] = participant.get("budget", 0) + e.get("buy_price", 0)
    return {"name": e["name"], "role": e.get("role", ""), "team": e.get("team", "")}


def resolve_sealed_bids(
    participants_by_name: dict[str, dict],
    player: dict,
    bids: list[dict],
    *,
    max_squad: int = 30,
) -> Optional[dict]:
    """Award ``player`` to the highest valid sealed bid.

    ``bids``: ``[{"participant", "amount"}]``. A bid is valid if the participant
    exists, can afford it, and has squad room. Ties break by earliest in the list.
    Returns the winning record, or None if no valid bid.
    """
    best = None
    for bid in sorted(bids, key=lambda b: -int(b.get("amount", 0))):
        p = participants_by_name.get(bid["participant"])
        if p is None:
            continue
        amount = int(bid.get("amount", 0))
        if amount <= 0 or amount > p.get("budget", 0):
            continue
        if len(p.get("squad", [])) >= max_squad:
            continue
        best = (p, amount)
        break
    if best is None:
        return None
    p, amount = best
    p["squad"].append({
        "name": player["name"], "role": player.get("role", ""),
        "team": player.get("team", ""), "buy_price": amount, "acquired_via": "market",
    })
    p["budget"] = p.get("budget", 0) - amount
    return {"type": "market_buy", "participant": p["name"], "player": player["name"], "amount": amount}
