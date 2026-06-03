"""Best-11 selection — ported from the legacy ``get_best_11`` (streamlit_app.py
lines 248-433).

Pure function: given a squad and per-player scores, pick the highest-scoring legal
XI under role-count constraints. Supports:
  * cricket (WK/BAT/AR/BWL) with gameweek-dependent ranges (gw <= 10 uses the
    older ranges), and football (GK/DEF/MID/FWD);
  * an Injury-Reserve player excluded only when the squad has >= 19 players;
  * dual-position players (score given as a ``{position: score}`` dict);
  * a greedy fallback that fills role minimums (padding empty slots with 0) when
    no fully-legal XI exists, returning explanatory warnings.

No framework imports; fully unit-tested.
"""

from __future__ import annotations

import itertools
from typing import Optional


def classify_cricket(role_str: str) -> str:
    r = (role_str or "").lower()
    if "wk" in r or "wicket" in r:
        return "WK"
    if "allrounder" in r or r == "ar":
        return "AR"
    if "bat" in r:
        return "BAT"
    if "bowl" in r:
        return "BWL"
    return "BAT"


def classify_football(role_str: str) -> str:
    r = (role_str or "").lower()
    if "gk" in r or "goalkeeper" in r:
        return "GK"
    if "def" in r or "back" in r or r in ("cb", "lb", "rb", "df"):
        return "DEF"
    if "mid" in r or r in ("cm", "dm", "am", "mf"):
        return "MID"
    if "fwd" in r or "forward" in r or "striker" in r or "winger" in r or r in (
        "fw", "cf", "lw", "rw", "st",
    ):
        return "FWD"
    return "MID"


def cricket_ranges(gameweek=None) -> dict[str, tuple[int, int]]:
    use_old = False
    if gameweek is not None:
        try:
            cleaned = "".join(c for c in str(gameweek) if c.isdigit())
            if cleaned and int(cleaned) <= 10:
                use_old = True
        except (ValueError, TypeError):
            pass
    if use_old:
        return {"WK": (1, 3), "BAT": (1, 4), "AR": (3, 6), "BWL": (2, 4)}
    return {"WK": (1, 3), "BAT": (1, 4), "AR": (2, 6), "BWL": (3, 4)}


FOOTBALL_RANGES = {"GK": (1, 1), "DEF": (3, 5), "MID": (3, 5), "FWD": (1, 3)}


def select_best_11(
    squad: list[dict],
    player_scores: dict,
    *,
    is_football: bool = False,
    ir_player: Optional[str] = None,
    gameweek=None,
) -> tuple[list[dict], list[str]]:
    """Return ``(best_team, warnings)``.

    ``squad`` is a list of ``{"name", "role"}``. ``player_scores`` maps name to a
    number, or to a ``{position: score}`` dict for dual-position players.
    """
    # IR only applies when the squad is full-size (>= 19); else everyone counts.
    if len(squad) < 19:
        ir_player = None
    active_squad = [p for p in squad if p["name"] != ir_player]

    classify = classify_football if is_football else classify_cricket

    scored_players: list[dict] = []
    for p in active_squad:
        entry = player_scores.get(p["name"], 0)
        if isinstance(entry, dict):
            for pos_key, pos_score in entry.items():
                scored_players.append(
                    {"name": p["name"], "role": p.get("role", ""),
                     "category": pos_key, "score": pos_score}
                )
        else:
            role_str = p.get("role", "") or ""
            scored_players.append(
                {"name": p["name"], "role": p.get("role", ""),
                 "category": classify(role_str), "score": entry}
            )

    # <= 11 unique players: return each at its best-scoring position.
    unique_names = {p["name"] for p in scored_players}
    if len(unique_names) <= 11:
        collapsed: dict[str, dict] = {}
        for p in scored_players:
            if p["name"] not in collapsed or p["score"] > collapsed[p["name"]]["score"]:
                collapsed[p["name"]] = p
        return list(collapsed.values()), []

    scored_players.sort(key=lambda x: x["score"], reverse=True)
    valid_ranges = FOOTBALL_RANGES if is_football else cricket_ranges(gameweek)

    best_team: list[dict] = []
    best_score = -1
    for team in itertools.combinations(scored_players, 11):
        names = [p["name"] for p in team]
        if len(set(names)) < 11:  # no player twice (dual-position guard)
            continue
        counts = {k: 0 for k in valid_ranges}
        total = 0
        for p in team:
            counts[p["category"]] += 1
            total += p["score"]
        if all(lo <= counts[r] <= hi for r, (lo, hi) in valid_ranges.items()):
            if total > best_score:
                best_score = total
                best_team = list(team)

    if best_team:
        return best_team, []

    # Greedy fallback: fill each role's minimum, pad missing with 0-point slots.
    range_str = ", ".join(f"{k}:{v[0]}-{v[1]}" for k, v in valid_ranges.items())
    warnings = [
        f"⚠️ Could not satisfy role constraints ({range_str}). "
        "Filling minimums with available players; empty slots score 0."
    ]
    collapsed = {}
    for p in scored_players:
        if p["name"] not in collapsed or p["score"] > collapsed[p["name"]]["score"]:
            collapsed[p["name"]] = p
    by_cat: dict[str, list[dict]] = {k: [] for k in valid_ranges}
    for p in collapsed.values():
        if p["category"] in by_cat:
            by_cat[p["category"]].append(p)
    for cat in by_cat:
        by_cat[cat].sort(key=lambda x: x["score"], reverse=True)

    greedy: list[dict] = []
    used: set[str] = set()
    for role, (lo, _) in valid_ranges.items():
        filled = 0
        for p in by_cat[role]:
            if filled >= lo:
                break
            if p["name"] not in used:
                greedy.append(p)
                used.add(p["name"])
                filled += 1
        while filled < lo:
            greedy.append({"name": f"[Empty {role} slot]", "role": role,
                           "category": role, "score": 0})
            filled += 1

    remaining = 11 - len(greedy)
    if remaining > 0:
        unused = [p for p in scored_players if p["name"] not in used]
        unused.sort(key=lambda x: x["score"], reverse=True)
        for p in unused:
            if remaining <= 0:
                break
            _, hi = valid_ranges.get(p["category"], (0, 99))
            if sum(1 for t in greedy if t["category"] == p["category"]) < hi:
                greedy.append(p)
                used.add(p["name"])
                remaining -= 1

    greedy.sort(key=lambda x: x["score"], reverse=True)
    return greedy[:11], warnings


def total_points(squad, player_scores, **kwargs) -> int:
    """Convenience: total of the best XI."""
    team, _ = select_best_11(squad, player_scores, **kwargs)
    return sum(p["score"] for p in team)
