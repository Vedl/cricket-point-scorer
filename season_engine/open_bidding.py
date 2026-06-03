"""Open bidding — deadline-resolved sealed/standing bids on unowned players.

Rules (owner spec):
  * minimum bid 5M;
  * once a player's bid reaches 50M, further bids must be in multiples of 5M;
  * a participant can never commit beyond their budget across ALL their leading
    bids (budget is reserved against every player they currently lead);
  * in the final window before the deadline, bids may only be RAISED in +5M steps
    (the room layer passes ``raise_only``);
  * all standing bids are awarded to the high bidder at the bidding deadline.

Pure functions over room-shaped dicts.
"""

from __future__ import annotations

MIN_BID = 5


class BidError(Exception):
    """An open-market bid was rejected (message is user-facing)."""


def min_next(open_bids: dict, player_name: str) -> int:
    cur = open_bids.get(player_name, {}).get("high_bid", 0)
    if cur == 0:
        return MIN_BID
    if cur >= 50:
        return cur + 5
    return cur + 1


def reserved(open_bids: dict, participant: str, exclude_player: str = None) -> int:
    """Total a participant has committed via the players they currently lead."""
    return sum(b["high_bid"] for pl, b in open_bids.items()
               if b["high_bidder"] == participant and pl != exclude_player)


def place_bid(participants_by_name: dict, open_bids: dict, player: dict, participant: str,
              amount: int, *, raise_only: bool = False, max_squad: int = 30) -> None:
    p = participants_by_name.get(participant)
    if p is None:
        raise BidError(f"Unknown participant {participant!r}.")
    if len(p.get("squad", [])) >= max_squad:
        raise BidError("Your squad is full.")
    amount = int(amount)
    name = player["name"]
    existing = name in open_bids

    if raise_only:
        if not existing:
            raise BidError("Bidding is closing — you can only raise existing bids now.")
        cur = open_bids[name]["high_bid"]
        if amount < cur + 5 or amount % 5 != 0:
            raise BidError("In the final window bids may only be raised in multiples of 5M.")
    else:
        need = min_next(open_bids, name)
        if amount < need:
            raise BidError(f"Bid must be at least {need}M.")
        if amount >= 50 and amount % 5 != 0:
            raise BidError("Bids of 50M or more must be in multiples of 5M.")

    available = p.get("budget", 0) - reserved(open_bids, participant, exclude_player=name)
    if amount > available:
        raise BidError(f"Bid exceeds your available budget ({available}M after outstanding bids).")

    open_bids[name] = {"high_bid": amount, "high_bidder": participant,
                       "role": player.get("role", ""), "team": player.get("team", "")}


def resolve_all(participants_by_name: dict, open_bids: dict, *, max_squad: int = 30) -> list[dict]:
    """Award every standing bid to its high bidder (called at the deadline)."""
    awarded = []
    for name in list(open_bids.keys()):
        bid = open_bids[name]
        p = participants_by_name.get(bid["high_bidder"])
        if p is not None and bid["high_bid"] <= p.get("budget", 0) and \
                len(p.get("squad", [])) < max_squad:
            p["squad"].append({"name": name, "role": bid.get("role", ""),
                               "team": bid.get("team", ""), "buy_price": bid["high_bid"],
                               "acquired_via": "market"})
            p["budget"] = p.get("budget", 0) - bid["high_bid"]
            awarded.append({"type": "market_buy", "participant": p["name"],
                            "player": name, "amount": bid["high_bid"]})
        del open_bids[name]
    return awarded


def active_bids(open_bids: dict) -> list[dict]:
    out = [{"player": n, "high_bid": b["high_bid"], "high_bidder": b["high_bidder"],
            "role": b.get("role", ""), "team": b.get("team", "")} for n, b in open_bids.items()]
    out.sort(key=lambda b: -b["high_bid"])
    return out
