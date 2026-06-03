"""Automated gameweek scoring from WhoScored match links.

Given the WhoScored links for a gameweek's matches, scrape each, compute per-player
fantasy points, and aggregate into ``room['gameweek_scores'][gw]``. Standings then
award points off each participant's *locked* squad for that gameweek (IR excluded).
This is the "automation" — the admin supplies the gameweek's match links and the
points are computed and stored in one action.
"""

from __future__ import annotations


def parse_links(text: str) -> list[str]:
    out = []
    for line in (text or "").splitlines():
        line = line.strip()
        if line.startswith("http"):
            out.append(line)
    return out


def score_gameweek_from_links(room: dict, gameweek: str, links: list[str]) -> tuple[dict, list[str]]:
    """Scrape each link, sum per-player points, store under the gameweek.

    Returns ``(player_points, errors)``. A player appearing in multiple matches in
    the gameweek has their points summed.
    """
    from scoring import whoscored_points

    totals: dict[str, int] = {}
    errors: list[str] = []
    for url in links:
        try:
            for r in whoscored_points(url):
                totals[r["player"]] = totals.get(r["player"], 0) + int(r["score"])
        except Exception as exc:  # network / bot-block / parse
            errors.append(f"{url[:60]}…: {exc}")
    if totals:
        room.setdefault("gameweek_scores", {})[str(gameweek)] = totals
    return totals, errors
