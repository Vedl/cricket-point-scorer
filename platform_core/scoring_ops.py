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


def _merge(existing, incoming):
    """Combine two player scores, each a number or a ``{pos: score}`` dict."""
    if existing is None:
        return incoming
    if isinstance(existing, dict) or isinstance(incoming, dict):
        a = existing if isinstance(existing, dict) else {"_": existing}
        b = incoming if isinstance(incoming, dict) else {"_": incoming}
        out = dict(a)
        for k, v in b.items():
            out[k] = out.get(k, 0) + v
        return out
    return existing + incoming


def _fifa_countries(room: dict) -> list[str]:
    """Distinct nations with a 'Keeper' entry available in this room."""
    from platform_core.config_layer import load_player_pool
    pool = (room.get("player_pool") and
            [{"name": p["name"], "team": p.get("team", "")} for p in room["player_pool"]]) or \
           [{"name": p.name, "team": p.team} for p in load_player_pool(room.get("tournament_type", ""))]
    return sorted({p["team"] for p in pool if p["name"].endswith(" Keeper")})


def _slugify(s: str) -> str:
    import re
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def _keeper_aliases(url: str, countries: list[str]) -> tuple[str, str]:
    """From a WhoScored URL, find the two nations (home, away) by slug order."""
    low = url.lower()
    hits = [(low.find(_slugify(c)), c) for c in countries if _slugify(c) and _slugify(c) in low]
    hits = [h for h in hits if h[0] >= 0]
    hits.sort()
    home = hits[0][1] if len(hits) >= 1 else None
    away = hits[1][1] if len(hits) >= 2 else None
    return home, away


def is_football_room(room: dict) -> bool:
    return room.get("tournament_type") == "FIFA World Cup 2026"


def fifa_countries(room: dict) -> list[str]:
    """Public wrapper: distinct nations with a 'Keeper' entry in this room."""
    return _fifa_countries(room)


def score_one_link(url: str, *, is_football: bool, countries: list[str]) -> dict:
    """Scrape ONE match link → ``{player_or_keeper_name: number | {pos: score}}``.

    Pure per-match scrape with no room mutation, so a caller can loop over the
    gameweek's links one at a time and report progress between matches.
    """
    from scoring import whoscored_keeper_scores, whoscored_player_scores

    out: dict = {}
    for name, sc in whoscored_player_scores(url).items():
        out[name] = _merge(out.get(name), sc)
    if is_football:
        ks = whoscored_keeper_scores(url)
        home, away = _keeper_aliases(url, countries)
        if home and ks.get("home") is not None:
            out[f"{home} Keeper"] = _merge(out.get(f"{home} Keeper"), ks["home"])
        if away and ks.get("away") is not None:
            out[f"{away} Keeper"] = _merge(out.get(f"{away} Keeper"), ks["away"])
    return out


def merge_link_totals(totals: dict, one: dict) -> None:
    """Fold one match's ``score_one_link`` result into the running gameweek totals."""
    for name, sc in one.items():
        totals[name] = _merge(totals.get(name), sc)


def score_gameweek_from_links(room: dict, gameweek: str, links: list[str]) -> tuple[dict, list[str]]:
    """Scrape each link, store per-player points (dual-position aware) under the
    gameweek. For football, each nation's goalkeeper points are stored under
    ``"{Country} Keeper"`` (keepers are owned per nation). Best-11 picks each
    player's best position from the ``{pos: score}`` dicts.
    """
    is_football = is_football_room(room)
    countries = fifa_countries(room) if is_football else []
    totals: dict = {}
    errors: list[str] = []
    for url in links:
        try:
            merge_link_totals(totals, score_one_link(url, is_football=is_football, countries=countries))
        except Exception as exc:  # network / bot-block / parse
            errors.append(f"{url[:60]}…: {exc}")
    if totals:
        room.setdefault("gameweek_scores", {})[str(gameweek)] = totals
    return totals, errors
