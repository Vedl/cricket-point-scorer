"""Scoring + scraping layer for the migrated app.

The legacy score calculators and schedule scrapers are already framework-free, so
they are reused as-is (PLAN.md §4 "ported as-is"). This package re-exports a clean
surface; heavy scraper deps are imported lazily so plain scoring needs only pandas.
"""

from player_score_calculator import CricketScoreCalculator

__all__ = ["CricketScoreCalculator", "football", "scrapers", "whoscored_points"]


def whoscored_points(url: str) -> list[dict]:
    """Scrape a WhoScored match link and return per-player fantasy points.

    Returns a list of ``{player, team, pos, score, minutes}`` sorted by score desc.
    Raises on scrape/parse failure (caller surfaces the message).
    """
    import math

    import football_score_calculator as f

    df = f.calc_all_players_whoscored(url)
    rows = []
    if df is None or getattr(df, "empty", True):
        return rows
    seen = set()
    for _, r in df.iterrows():
        name = str(r.get("Player", "") or "")
        pos = str(r.get("Position", "") or "")
        key = (name, pos)
        if not name or key in seen:
            continue
        seen.add(key)
        try:
            score = int(round(float(r.get("Score") or 0)))
        except (TypeError, ValueError):
            score = 0
        mins = r.get("minutes_played", 0)
        try:
            mins = 0 if (mins is None or (isinstance(mins, float) and math.isnan(mins))) else int(mins)
        except (TypeError, ValueError):
            mins = 0
        rows.append({"player": name, "team": str(r.get("Team", "") or ""),
                     "pos": pos, "score": score, "minutes": mins})
    rows.sort(key=lambda x: x["score"], reverse=True)
    return rows


def __getattr__(name):
    # Lazy access to optional heavy modules.
    if name == "football":
        import football_score_calculator as football
        return football
    if name == "scrapers":
        import types
        mod = types.ModuleType("scrapers")
        import cricbuzz_scraper
        mod.CricbuzzScraper = cricbuzz_scraper.CricbuzzScraper
        return mod
    raise AttributeError(name)
