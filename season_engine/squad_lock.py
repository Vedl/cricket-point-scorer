"""Squad-lock pipeline (per participant) — IR + 19-player cap rules.

Applied to each participant when a gameweek's squads are locked:

  1. If the squad has more than ``max_squad`` (19) players, the cheapest are
     released (for FREE — no refund) until 19 remain. Joint-cheapest players are
     chosen at random. Players on loan TO this participant are never auto-released
     (they belong to someone else and return at the next gameweek).
  2. Injury Reserve: if the squad is full (>= 19) and the participant set no
     (valid) IR, their most expensive player is auto-assigned to IR — joint-most
     expensive broken at random.
  3. The IR fee (``ir_cost``, 2M) and the Best-11 bench only bind for a FULL
     squad (>= 19 players) — owner rule: an IR on a smaller squad is ignored
     entirely (no fee, the player still counts). If the participant can't afford
     the fee, the IR player is released and the IR slot cleared.

Pure: mutates the passed participant dict, returns ``(released_entries, notes)``.
"""

from __future__ import annotations

import random

MAX_SQUAD = 19
IR_COST = 2


def _entry(squad, name):
    return next((e for e in squad if e["name"] == name), None)


def _price(e) -> float:
    try:
        return float(e.get("buy_price", 0) or 0)
    except (TypeError, ValueError):
        return 0.0


def lock_participant(p: dict, *, max_squad: int = MAX_SQUAD, ir_cost: int = IR_COST):
    released: list[dict] = []
    notes: list[str] = []
    squad = p.setdefault("squad", [])

    # 1. Trim to the cap by releasing the cheapest players (random among ties).
    #    Loaned-in players are skipped: the borrower doesn't own them.
    while len(squad) > max_squad:
        own = [e for e in squad if e.get("acquired_via") != "loan"] or list(squad)
        low = min(_price(e) for e in own)
        dropped = random.choice([e for e in own if _price(e) == low])
        squad.remove(dropped)
        released.append(dropped)
        notes.append(f"Released cheapest: {dropped['name']} (over {max_squad}, no refund).")

    # 2. IR is mandatory for a full squad (>= max_squad players). If the squad is
    #    full and no valid IR is set, the most expensive player is benched
    #    (joint-most expensive broken at random).
    ir = p.get("ir")
    if _entry(squad, ir) is None:
        ir = None  # stale / unset
    if ir is None and len(squad) >= max_squad and squad:
        high = max(_price(e) for e in squad)
        ir = random.choice([e for e in squad if _price(e) == high])["name"]
        notes.append(f"No IR set — most expensive ({ir}) placed in IR.")
    p["ir"] = ir

    # 3. The IR fee only applies to a full squad (>= 19), where IR is real.
    #    For smaller squads the IR is ignored (no fee, counts in Best-11).
    if p.get("ir") and len(squad) >= max_squad:
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
