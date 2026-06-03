"""Market + trading operations over the room document.

Bridges the room schema (``participants``, ``pending_trades``, ``unsold_players``,
``active_bids``, ``transactions``) to the pure ``season_engine`` trade/market
functions. Pure dict ops; persistence is the caller's job.
"""

from __future__ import annotations

import uuid

from season_engine.market import release_player, resolve_sealed_bids
from season_engine.trading import TradeError, apply_trade, validate_trade

MAX_SQUAD = 30


def participants_by_name(room: dict) -> dict[str, dict]:
    return {p["name"]: p for p in room.get("participants", [])}


def _log(room: dict, rec: dict) -> None:
    room.setdefault("transactions", []).append(rec)


# --- trades -------------------------------------------------------------- #
def propose_trade(room, from_name, to_name, give_players, get_players,
                  give_cash=0, get_cash=0) -> str:
    by = participants_by_name(room)
    if from_name not in by or to_name not in by:
        raise TradeError("Both participants must exist.")
    if from_name == to_name:
        raise TradeError("You can't trade with yourself.")
    errors = validate_trade(by[from_name], by[to_name], give_players, get_players,
                            give_cash, get_cash, max_squad=MAX_SQUAD)
    if errors:
        raise TradeError(" ".join(errors))
    tid = uuid.uuid4().hex[:8]
    room.setdefault("pending_trades", []).append({
        "id": tid, "from": from_name, "to": to_name,
        "give_players": list(give_players), "get_players": list(get_players),
        "give_cash": int(give_cash), "get_cash": int(get_cash), "status": "pending",
    })
    return tid


def incoming_trades(room, name):
    return [t for t in room.get("pending_trades", []) if t["to"] == name and t["status"] == "pending"]


def outgoing_trades(room, name):
    return [t for t in room.get("pending_trades", []) if t["from"] == name and t["status"] == "pending"]


def _find_trade(room, trade_id):
    return next((t for t in room.get("pending_trades", []) if t["id"] == trade_id), None)


def accept_trade(room, trade_id) -> dict:
    t = _find_trade(room, trade_id)
    if t is None or t["status"] != "pending":
        raise TradeError("Trade not found or already resolved.")
    by = participants_by_name(room)
    rec = apply_trade(by[t["from"]], by[t["to"]], t["give_players"], t["get_players"],
                      t["give_cash"], t["get_cash"], max_squad=MAX_SQUAD)
    t["status"] = "accepted"
    _log(room, rec)
    return rec


def reject_trade(room, trade_id) -> None:
    t = _find_trade(room, trade_id)
    if t is not None:
        t["status"] = "rejected"


# --- releases + open market --------------------------------------------- #
def release(room, name, player_name, *, refund=False) -> dict:
    by = participants_by_name(room)
    if name not in by:
        raise TradeError("Unknown participant.")
    rec = release_player(by[name], player_name, refund=refund)
    pool = room.setdefault("unsold_players", [])
    if not any((p.get("name") if isinstance(p, dict) else p) == rec["name"] for p in pool):
        pool.append(rec)
    _log(room, {"type": "release", "participant": name, "player": player_name, "refund": refund})
    return rec


def available_players(room) -> list[dict]:
    out = []
    for p in room.get("unsold_players", []):
        out.append(p if isinstance(p, dict) else {"name": p, "role": "", "team": ""})
    return out


def place_market_bid(room, name, player_name, amount) -> None:
    by = participants_by_name(room)
    if name not in by:
        raise TradeError("Unknown participant.")
    amount = int(amount)
    if amount <= 0 or amount > by[name].get("budget", 0):
        raise TradeError("Bid exceeds your budget.")
    bids = room.setdefault("active_bids", [])
    # one bid per (player, participant): replace
    bids[:] = [b for b in bids if not (b["player"] == player_name and b["participant"] == name)]
    bids.append({"player": player_name, "participant": name, "amount": amount})


def resolve_market(room, player_name) -> dict | None:
    by = participants_by_name(room)
    player = next((p for p in available_players(room) if p["name"] == player_name), None)
    if player is None:
        return None
    bids = [b for b in room.get("active_bids", []) if b["player"] == player_name]
    rec = resolve_sealed_bids(by, player, bids, max_squad=MAX_SQUAD)
    # clear this player's bids + remove from pool if sold
    room["active_bids"] = [b for b in room.get("active_bids", []) if b["player"] != player_name]
    if rec is not None:
        room["unsold_players"] = [
            p for p in room.get("unsold_players", [])
            if (p.get("name") if isinstance(p, dict) else p) != player_name
        ]
        _log(room, rec)
    return rec


def transactions(room) -> list[dict]:
    return room.get("transactions", [])
