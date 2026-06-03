"""Open bidding — asynchronous 24h standing-bid market on remaining players.

After the (off-app, Zoom) live auction, every player not already owned is up for
open bidding. A participant bids; the highest bid must *stand* for a window
(default 24h) to win. Any higher bid resets that window. When the window elapses
with no higher bid, the player is awarded to the high bidder (budget + squad cap
enforced). Pure functions over room-shaped dicts; time is injected.
"""

from __future__ import annotations

WINDOW_SECONDS = 24 * 60 * 60  # 24 hours


class BidError(Exception):
    """An open-market bid was rejected (message is user-facing)."""


def min_next(open_bids: dict, player_name: str) -> int:
    cur = open_bids.get(player_name)
    return (cur["high_bid"] + 1) if cur else 1


def place_bid(
    participants_by_name: dict,
    open_bids: dict,
    player: dict,
    participant: str,
    amount: int,
    now: float,
    *,
    window: int = WINDOW_SECONDS,
    max_squad: int = 30,
) -> None:
    """Place/raise a standing bid on ``player``. Resets the 24h window."""
    p = participants_by_name.get(participant)
    if p is None:
        raise BidError(f"Unknown participant {participant!r}.")
    if len(p.get("squad", [])) >= max_squad:
        raise BidError("Your squad is full.")
    amount = int(amount)
    need = min_next(open_bids, player["name"])
    if amount < need:
        raise BidError(f"Bid must be at least {need}M.")
    if amount > p.get("budget", 0):
        raise BidError(f"Bid exceeds your budget ({p.get('budget', 0)}M).")
    open_bids[player["name"]] = {
        "high_bid": amount,
        "high_bidder": participant,
        "ends_at": now + window,
        "role": player.get("role", ""),
        "team": player.get("team", ""),
    }


def resolve_due(
    participants_by_name: dict,
    open_bids: dict,
    now: float,
    *,
    max_squad: int = 30,
) -> list[dict]:
    """Award every bid whose window has elapsed. Returns transaction records."""
    awarded: list[dict] = []
    for name in list(open_bids.keys()):
        bid = open_bids[name]
        if now < bid["ends_at"]:
            continue
        p = participants_by_name.get(bid["high_bidder"])
        if p is not None and bid["high_bid"] <= p.get("budget", 0) and \
                len(p.get("squad", [])) < max_squad:
            p["squad"].append({
                "name": name, "role": bid.get("role", ""), "team": bid.get("team", ""),
                "buy_price": bid["high_bid"], "acquired_via": "market",
            })
            p["budget"] = p.get("budget", 0) - bid["high_bid"]
            awarded.append({"type": "market_buy", "participant": p["name"],
                            "player": name, "amount": bid["high_bid"]})
        del open_bids[name]
    return awarded


def active_bids(open_bids: dict, now: float) -> list[dict]:
    """Current standing bids with seconds remaining, soonest-closing first."""
    out = []
    for name, bid in open_bids.items():
        out.append({
            "player": name, "high_bid": bid["high_bid"], "high_bidder": bid["high_bidder"],
            "remaining": max(0, int(bid["ends_at"] - now)),
            "role": bid.get("role", ""), "team": bid.get("team", ""),
        })
    out.sort(key=lambda b: b["remaining"])
    return out
