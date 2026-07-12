"""Open bidding — deadline-resolved sealed/standing bids on unowned players.

Rules (owner spec):
  * minimum bid 5M;
  * once a player's bid reaches 50M, further bids must be in multiples of 5M;
  * a participant can never commit beyond their budget across ALL their leading
    bids (budget is reserved against every player they currently lead);
  * in the final window before the deadline, bids may only be RAISED in exact +5M steps
    (the room layer passes ``raise_only``); anything past 50M must be a multiple of 5M,
    so a 46/47/48/49M bid jumps straight to 55M;
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


def raise_only_next(cur: int) -> int:
    """Minimum valid raise in the final (raise-only) window.

    Bids step up by exactly 5M, EXCEPT that any amount past 50M must be a multiple of
    5M — so a bid sitting at 46/47/48/49M (where +5 would land on 51-54M) jumps straight
    to 55M. Below 50M the +5 step is kept as-is, even if the current bid isn't itself a
    multiple of 5 (it may have reached an odd value via +1 bids in an earlier window)."""
    nxt = cur + 5
    if nxt > 50 and nxt % 5 != 0:
        nxt += 5 - (nxt % 5)
    return nxt


def reserved(open_bids: dict, participant: str, exclude_player: str = None) -> int:
    """Total a participant has committed via the players they currently lead."""
    return sum(b["high_bid"] for pl, b in open_bids.items()
               if b["high_bidder"] == participant and pl != exclude_player)


def place_bid(participants_by_name: dict, open_bids: dict, player: dict, participant: str,
              amount: int, expires_iso: str, *, raise_only: bool = False, max_squad: int = 30) -> None:
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
        need = raise_only_next(cur)
        if amount < need:
            raise BidError(f"In the final window you must raise to at least {need}M.")
        if amount > 50 and amount % 5 != 0:
            raise BidError("Above 50M, bids must be in multiples of 5M.")
        if amount <= 50 and (amount - cur) % 5 != 0:
            raise BidError("In the final window bids go up in exact 5M steps.")
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
                       "role": player.get("role", ""), "team": player.get("team", ""),
                       "expires": expires_iso}


def resolve_expired(participants_by_name: dict, open_bids: dict, now_iso: str, *, max_squad: int = 30) -> list[dict]:
    """Award standing bids where the expiration time has been reached or passed."""
    awarded = []
    for name in list(open_bids.keys()):
        bid = open_bids[name]
        if now_iso < bid.get("expires", now_iso):
            continue  # not yet expired
            
        p = participants_by_name.get(bid["high_bidder"])
        # An eliminated team never wins a player, even if a stale standing bid
        # survived to award time — drop it like an over-budget/full-squad bid.
        if p is not None and not p.get("is_eliminated") and \
                bid["high_bid"] <= p.get("budget", 0) and \
                len(p.get("squad", [])) < max_squad:
            p["squad"].append({"name": name, "role": bid.get("role", ""),
                               "team": bid.get("team", ""), "buy_price": bid["high_bid"],
                               "acquired_via": "market"})
            p["budget"] = p.get("budget", 0) - bid["high_bid"]
            awarded.append({"ts": now_iso, "type": "market_buy", "participant": p["name"],
                            "player": name, "amount": bid["high_bid"]})
        del open_bids[name]
    return awarded


def active_bids(open_bids: dict) -> list[dict]:
    out = [{"player": n, "high_bid": b["high_bid"], "high_bidder": b["high_bidder"],
            "role": b.get("role", ""), "team": b.get("team", ""), "expires": b.get("expires", "")} for n, b in open_bids.items()]
    out.sort(key=lambda b: -b["high_bid"])
    return out
