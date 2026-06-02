"""Knockout elimination — ported from the legacy tournament-knockout feature.

Each knockout round ranks the still-active participants by their Best-11 gameweek
score (lowest = eliminated). Pure functions over standings rows; the caller marks
participants eliminated and persists.
"""

from __future__ import annotations


def select_for_elimination(
    standings: list[dict],
    *,
    count: int = 1,
    already_eliminated: set[str] | None = None,
) -> list[str]:
    """Return the names of the bottom ``count`` *active* participants.

    ``standings``: rows with ``{"participant", "points"}`` (any order).
    Participants already eliminated are skipped.
    """
    already = already_eliminated or set()
    active = [r for r in standings if r["participant"] not in already]
    # Lowest points first; stable so ties break by given order.
    active_sorted = sorted(active, key=lambda r: r["points"])
    return [r["participant"] for r in active_sorted[: max(0, count)]]


def survivors(standings: list[dict], eliminated: set[str]) -> list[str]:
    return [r["participant"] for r in standings if r["participant"] not in eliminated]
