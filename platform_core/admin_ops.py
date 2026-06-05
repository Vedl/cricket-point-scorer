"""Admin micro-operations over the room document.

Force add/release, budget edits, PIN reset, loans + reverse-loan, reset/delete
room, and backup/restore. Pure dict operations; persistence is the caller's job.
"""

from __future__ import annotations

import json
import uuid

from .config_layer import DEFAULT_BUDGET

MAX_SQUAD = 30


class AdminError(Exception):
    """An admin operation failed (message is user-facing)."""


def _by(room):
    return {p["name"]: p for p in room.get("participants", [])}


def _entry(p, player_name):
    return next((e for e in p.get("squad", []) if e["name"].lower() == player_name.lower()), None)


# --- roster overrides ---------------------------------------------------- #
def force_add_player(room, participant, player_name, role="", team="", price=0):
    by = _by(room)
    p = by.get(participant)
    if p is None:
        raise AdminError(f"Unknown team {participant!r}.")
    if _entry(p, player_name):
        raise AdminError(f"{participant} already has {player_name}.")
    if len(p.get("squad", [])) >= MAX_SQUAD:
        raise AdminError(f"{participant}'s squad is full.")
    p.setdefault("squad", []).append({
        "name": player_name, "role": role, "team": team,
        "buy_price": int(price or 0), "acquired_via": "admin",
    })
    p["budget"] = p.get("budget", 0) - int(price or 0)


def force_release(room, participant, player_name, *, refund=False):
    by = _by(room)
    p = by.get(participant)
    if p is None:
        raise AdminError(f"Unknown team {participant!r}.")
    e = _entry(p, player_name)
    if e is None:
        raise AdminError(f"{participant} doesn't have {player_name}.")
    p["squad"].remove(e)
    if refund:
        p["budget"] = p.get("budget", 0) + e.get("buy_price", 0)


def boost_all(room, amount=100) -> int:
    """Add ``amount`` (M) to every participant's budget. Returns count boosted."""
    parts = room.get("participants", [])
    for p in parts:
        p["budget"] = p.get("budget", 0) + int(amount)
    room["manual_boost_applied"] = True
    return len(parts)


def adjust_budget(room, participant, delta):
    by = _by(room)
    p = by.get(participant)
    if p is None:
        raise AdminError(f"Unknown team {participant!r}.")
    p["budget"] = p.get("budget", 0) + int(delta)


def reset_pin(room, participant, new_pin):
    by = _by(room)
    p = by.get(participant)
    if p is None:
        raise AdminError(f"Unknown team {participant!r}.")
    p["pin"] = str(new_pin).strip()


def rename_team(room: dict, old_name: str, new_name: str) -> None:
    """Rename a participant and update all their historical and active references."""
    new_name = new_name.strip()
    if not new_name:
        raise AdminError("Team name cannot be empty.")
    if any(p["name"].lower() == new_name.lower() for p in room.get("participants", [])):
        raise AdminError(f"A team named '{new_name}' already exists.")
        
    found = False
    for p in room.get("participants", []):
        if p["name"] == old_name:
            p["name"] = new_name
            found = True
            break
            
    if not found:
        raise AdminError(f"Team '{old_name}' not found.")
        
    for b in room.get("active_bids", []):
        if b.get("highest_bidder") == old_name:
            b["highest_bidder"] = new_name
            
    for t in room.get("pending_trades", []):
        if t.get("proposer") == old_name:
            t["proposer"] = new_name
        if t.get("target_team") == old_name:
            t["target_team"] = new_name
            
    for t in room.get("transactions", []):
        if t.get("participant") == old_name:
            t["participant"] = new_name
            
    for log in room.get("auction_log", []):
        if log.get("buyer") == old_name:
            log["buyer"] = new_name
            
    for gw, squads in room.get("gameweek_squads", {}).items():
        if old_name in squads:
            squads[new_name] = squads.pop(old_name)
            
    for gw, scores in room.get("gameweek_scores", {}).items():
        if old_name in scores:
            scores[new_name] = scores.pop(old_name)
            
    for l in room.get("active_loans", []):
        if l.get("from") == old_name:
            l["from"] = new_name
        if l.get("to") == old_name:
            l["to"] = new_name


def distribute_pins(room) -> list[dict]:
    """Auto-generate unique 4-digit PINs for every team that has no PIN.

    Returns a list of ``{"name": ..., "pin": ...}`` for ALL participants so the
    admin can share the complete list.
    """
    import random

    existing_pins: set[str] = set()
    for p in room.get("participants", []):
        pin = str(p.get("pin") or "").strip()
        if pin:
            existing_pins.add(pin)

    for p in room.get("participants", []):
        pin = str(p.get("pin") or "").strip()
        if not pin and not p.get("user"):
            # Generate a unique 4-digit PIN
            while True:
                new_pin = f"{random.randint(0, 9999):04d}"
                if new_pin not in existing_pins:
                    break
            p["pin"] = new_pin
            existing_pins.add(new_pin)

    return [{"name": p["name"], "pin": str(p.get("pin") or "—")}
            for p in room.get("participants", [])]


# --- loans --------------------------------------------------------------- #
def loan_player(room, from_name, to_name, player_name, return_gameweek=""):
    by = _by(room)
    if from_name not in by or to_name not in by:
        raise AdminError("Both teams must exist.")
    e = _entry(by[from_name], player_name)
    if e is None:
        raise AdminError(f"{from_name} doesn't have {player_name}.")
    by[from_name]["squad"].remove(e)
    moved = {**e, "acquired_via": "loan"}
    by[to_name].setdefault("squad", []).append(moved)
    lid = uuid.uuid4().hex[:8]
    room.setdefault("active_loans", []).append({
        "id": lid, "from": from_name, "to": to_name, "player": player_name,
        "return_gameweek": str(return_gameweek), "entry": dict(e),
    })
    return lid


def reverse_loan(room, loan_id):
    loans = room.get("active_loans", [])
    loan = next((l for l in loans if l["id"] == loan_id), None)
    if loan is None:
        raise AdminError("Loan not found.")
    by = _by(room)
    cur = _entry(by.get(loan["to"], {"squad": []}), loan["player"])
    if cur is not None:
        by[loan["to"]]["squad"].remove(cur)
    by[loan["from"]].setdefault("squad", []).append(loan["entry"])
    loans.remove(loan)
    return loan["player"]


# --- room lifecycle ------------------------------------------------------ #
def reset_room(room):
    """Wipe auction/season progress; keep teams + PINs + members."""
    from auction_engine import AuctionState
    for p in room.get("participants", []):
        p["squad"] = []
        p["budget"] = DEFAULT_BUDGET
        p["is_eliminated"] = False
    room["auction_state"] = AuctionState().to_dict()
    for key in ("bid_log", "unsold_players", "active_bids", "pending_trades",
                "transactions", "knockout_history", "active_loans"):
        room[key] = []
    for key in ("gameweek_scores", "gameweek_squads"):
        room[key] = {}
    room["current_gameweek"] = 0


def export_room(room) -> str:
    return json.dumps(room, indent=2)


def import_room(doc, code, json_text) -> None:
    try:
        data = json.loads(json_text)
    except json.JSONDecodeError as exc:
        raise AdminError(f"Invalid JSON: {exc}")
    if not isinstance(data, dict) or "participants" not in data:
        raise AdminError("That doesn't look like a room export.")
    doc.setdefault("rooms", {})[code.upper()] = data


def delete_room(doc, code) -> None:
    code = code.upper()
    doc.get("rooms", {}).pop(code, None)
    for u in doc.get("users", {}).values():
        for key in ("rooms_created", "rooms_joined"):
            if isinstance(u.get(key), list) and code in u[key]:
                u[key].remove(code)
