"""Standings — per-gameweek and cumulative, via Best-11.

Ports the leaderboard logic from the legacy app (backend/engine.py
``calculate_leaderboard`` / ``calculate_cumulative_leaderboard`` and the Streamlit
standings views): each participant's gameweek score is the sum of their Best-11 for
that gameweek; the cumulative score sums those per-gameweek Best-11 totals.

Pure functions over plain dicts; no framework imports.
"""

from __future__ import annotations

from typing import Optional

from .best11 import select_best_11


def participant_gw_points(
    squad: list[dict],
    gw_scores: dict,
    *,
    is_football: bool,
    gameweek=None,
    ir_player: Optional[str] = None,
    enforce_ir: bool = False,
) -> tuple[int, list[dict], list[str]]:
    """Return ``(points, best_11, warnings)`` for one participant in one gameweek."""
    team, warnings = select_best_11(
        squad, gw_scores, is_football=is_football, gameweek=gameweek,
        ir_player=ir_player, enforce_ir=enforce_ir,
    )
    return sum(p["score"] for p in team), team, warnings


def gameweek_standings(
    participants: list[dict],
    gw_scores: dict,
    *,
    is_football: bool,
    gameweek=None,
    enforce_ir: bool = False,
) -> list[dict]:
    """Ranked standings for a single gameweek.

    ``participants``: ``[{"name", "squad": [{"name","role"}], "ir"?}]``.
    Returns rows sorted by points desc: ``{participant, points, best_11, warnings}``.
    """
    rows = []
    for p in participants:
        pts, team, warns = participant_gw_points(
            p.get("squad", []), gw_scores, is_football=is_football,
            gameweek=gameweek, ir_player=p.get("ir"), enforce_ir=enforce_ir,
        )
        rows.append(
            {"participant": p["name"], "points": pts, "best_11": team, "warnings": warns}
        )
    rows.sort(key=lambda r: r["points"], reverse=True)
    return rows


def cumulative_standings(
    participants: list[dict],
    all_gw_scores: dict,
    *,
    is_football: bool,
    squads_by_gw: Optional[dict] = None,
    enforce_ir: bool = False,
) -> list[dict]:
    """Cumulative standings = sum of each participant's per-gameweek Best-11.

    ``all_gw_scores``: ``{gameweek: {player_name: score}}``.
    ``squads_by_gw`` (optional): ``{gameweek: {participant_name: squad}}`` to use the
    *locked* squad snapshot for a gameweek; falls back to the current squad.
    """
    totals = {p["name"]: 0 for p in participants}
    breakdown = {p["name"]: {} for p in participants}

    for gw, scores in all_gw_scores.items():
        # Build the participant list for this gameweek (locked squad if available).
        gw_participants = []
        for p in participants:
            squad = p.get("squad", [])
            ir = p.get("ir")
            if squads_by_gw and gw in squads_by_gw and p["name"] in squads_by_gw[gw]:
                snap = squads_by_gw[gw][p["name"]]
                squad = snap.get("squad", snap) if isinstance(snap, dict) else snap
                if isinstance(snap, dict):
                    ir = snap.get("ir", ir)
            gw_participants.append({"name": p["name"], "squad": squad, "ir": ir})

        for row in gameweek_standings(gw_participants, scores, is_football=is_football,
                                      gameweek=gw, enforce_ir=enforce_ir):
            totals[row["participant"]] += row["points"]
            breakdown[row["participant"]][str(gw)] = row["points"]

    rows = [
        {"participant": n, "points": totals[n], "by_gameweek": breakdown[n]}
        for n in totals
    ]
    rows.sort(key=lambda r: r["points"], reverse=True)
    return rows


def top_n(standings: list[dict], n: int = 3) -> list[dict]:
    return standings[:n]
