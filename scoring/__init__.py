"""Scoring + scraping layer for the migrated app.

The legacy score calculators and schedule scrapers are already framework-free, so
they are reused as-is (PLAN.md §4 "ported as-is"). This package re-exports a clean
surface; heavy scraper deps are imported lazily so plain scoring needs only pandas.
"""

__all__ = ["CricketScoreCalculator", "football", "scrapers", "whoscored_points",
           "whoscored_player_scores"]
# CricketScoreCalculator (which pulls pandas/numpy) is exposed lazily via __getattr__
# below, so merely importing `scoring` does NOT load pandas at app startup — keeping
# the backend's boot light/fast on the tiny free VM.

_POS_CACHE: dict = {}


def _json_pos_map() -> dict:
    """name -> registered position (GK/DEF/MID/FWD) from fifa_wc_2026_players.json."""
    if _POS_CACHE:
        return _POS_CACHE
    import json
    import os
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "fifa_wc_2026_players.json")
    try:
        data = json.load(open(path))
    except Exception:
        data = []
    from scoring.positions import map_role_to_pos

    for p in data:
        if not isinstance(p, dict):
            continue
        pos = map_role_to_pos(p.get("role") or p.get("position") or "")
        if pos and p.get("name"):
            _POS_CACHE[p["name"]] = pos
    return _POS_CACHE


def _scrape_grouped(url: str):
    """Return ``{player: {"team", "minutes", "by_pos": {pos: score}}}`` for a match."""
    import math

    import football_score_calculator as f

    df = f.calc_all_players_whoscored(url)
    out: dict = {}
    if df is None or getattr(df, "empty", True):
        return out
    for _, r in df.iterrows():
        name = str(r.get("Player", "") or "")
        if not name:
            continue
        pos = str(r.get("Position", "") or "")
        try:
            score = int(round(float(r.get("Score") or 0)))
        except (TypeError, ValueError):
            score = 0
        mins = r.get("minutes_played", 0)
        try:
            mins = 0 if (mins is None or (isinstance(mins, float) and math.isnan(mins))) else int(mins)
        except (TypeError, ValueError):
            mins = 0
        e = out.setdefault(name, {"team": str(r.get("Team", "") or ""), "minutes": mins, "by_pos": {}})
        if pos:
            e["by_pos"][pos] = score
        e["minutes"] = max(e["minutes"], mins)
    return out


def whoscored_points(url: str) -> list[dict]:
    """Per-player display rows: ``{player, team, pos, score, minutes}`` sorted desc.

    A player's position is their REGISTERED position from the squad database when
    known (so substitutes show their real position, not a generic "MID"); the score
    is that position's score.
    """
    pos_map = _json_pos_map()
    rows = []
    for name, e in _scrape_grouped(url).items():
        by_pos = e["by_pos"]
        reg = pos_map.get(name)
        if reg and reg in by_pos:
            pos, score = reg, by_pos[reg]
        elif reg:
            pos = reg
            score = max(by_pos.values()) if by_pos else 0
        else:
            # not in DB: best-scoring position WhoScored gave (avoid defaulting to MID)
            pos, score = max(by_pos.items(), key=lambda kv: kv[1]) if by_pos else ("", 0)
        rows.append({"player": name, "team": e["team"], "pos": pos,
                     "score": score, "minutes": e["minutes"]})
    rows.sort(key=lambda x: x["score"], reverse=True)
    return rows


def whoscored_keeper_scores(url: str) -> dict:
    """Return ``{"home": gk_score, "away": gk_score}`` for a match — the points of
    each side's goalkeeper (highest-minutes GK). Used for nation "Keeper" entries.
    """
    res = {"home": None, "away": None}
    best_min = {"home": -1, "away": -1}
    # _scrape_grouped collapses minutes; re-scan for GK with most minutes per side.
    import football_score_calculator as f
    df = f.calc_all_players_whoscored(url)
    if df is None or getattr(df, "empty", True):
        return res
    for _, r in df.iterrows():
        pos = str(r.get("Position", "") or "")
        if pos != "GK":
            continue
        side = str(r.get("Team", "") or "").lower()
        if side not in ("home", "away"):
            continue
        try:
            mins = int(r.get("minutes_played", 0) or 0)
        except (TypeError, ValueError):
            mins = 0
        try:
            score = int(round(float(r.get("Score") or 0)))
        except (TypeError, ValueError):
            score = 0
        if mins > best_min[side]:
            best_min[side] = mins
            res[side] = score
    return res


def whoscored_player_scores(url: str) -> dict:
    """For gameweek scoring: ``{player: number | {pos: score}}``.

    Players who can score in more than one position return a ``{pos: score}`` dict
    so Best-11 can place them where it most helps the formation (the dual-position
    rule). Single-position players return a plain number.
    """
    out = {}
    for name, e in _scrape_grouped(url).items():
        by_pos = e["by_pos"]
        if not by_pos:
            continue
        out[name] = next(iter(by_pos.values())) if len(by_pos) == 1 else dict(by_pos)
    return out


def __getattr__(name):
    # Lazy access to optional heavy modules.
    if name == "CricketScoreCalculator":
        from player_score_calculator import CricketScoreCalculator
        return CricketScoreCalculator
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
