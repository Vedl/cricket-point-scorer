"""Squad-lock pipeline (per participant) — IR + 19-player cap rules.

Applied to each participant when a gameweek's squads are locked:

  1. If the squad has more than ``max_squad`` (19) players, the cheapest are
     released until 19 remain.
  2. Injury Reserve: if the participant set no (valid) IR, their most expensive
     player is auto-assigned to IR. The IR player's points don't count (handled in
     Best-11) and costs ``ir_cost`` (2M) at lock. If they can't afford the 2M, the
     IR player is released and the IR slot cleared.

Pure: mutates the passed participant dict, returns ``(released_entries, notes)``.
"""

from __future__ import annotations

MAX_SQUAD = 19
IR_COST = 2


def _entry(squad, name):
    return next((e for e in squad if e["name"] == name), None)


def lock_participant(p: dict, *, max_squad: int = MAX_SQUAD, ir_cost: int = IR_COST):
    released: list[dict] = []
    notes: list[str] = []
    squad = p.setdefault("squad", [])

    # 1. Trim to the cap by releasing the cheapest players.
    if len(squad) > max_squad:
        squad.sort(key=lambda e: e.get("buy_price", 0))  # cheapest first
        while len(squad) > max_squad:
            dropped = squad.pop(0)
            released.append(dropped)
            notes.append(f"Released cheapest: {dropped['name']} (over {max_squad}).")

    # 2. Auto-assign IR if none set (or the set IR is no longer in the squad).
    ir = p.get("ir")
    if not ir or _entry(squad, ir) is None:
        if squad:
            ir = max(squad, key=lambda e: e.get("buy_price", 0))["name"]
            p["ir"] = ir
            notes.append(f"No IR set — most expensive ({ir}) placed in IR.")
        else:
            p["ir"] = None
            ir = None

    # 3. Charge the IR fee; if unaffordable, release the IR player.
    if p.get("ir"):
        if p.get("budget", 0) >= ir_cost:
            p["budget"] = p.get("budget", 0) - ir_cost
            notes.append(f"IR fee {ir_cost}M charged ({p['ir']} benched).")
        else:
            e = _entry(squad, p["ir"])
            if e is not None:
                squad.remove(e)
                released.append(e)
                notes.append(f"Couldn't afford IR fee — released {p['ir']}.")
            p["ir"] = None

    return released, notes
