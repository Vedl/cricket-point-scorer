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


def _norm_tokens(s: str) -> list[str]:
    """Lowercase, accent-stripped tokens split on any non-alphanumeric run — so a
    URL slug and a nation name tokenise the same way (hyphens are separators here,
    unlike player-name canonicalisation which joins across them)."""
    import re
    import unicodedata
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = "".join(c for c in s if not unicodedata.combining(c)).casefold()
    return [t for t in re.split(r"[^a-z0-9]+", s) if t]


# Pool nation names that share no full token with their WhoScored URL slug — map
# the token form of the pool name to the distinctive slug token(s).
_COUNTRY_SLUG_ALIASES = {
    "korea republic": {"korea"},        # url: ...-south-korea-...
    "ir iran": {"iran"},                # url: ...-iran-...
    "cote d ivoire": {"ivory", "coast"},  # url: ...-ivory-coast-...
}


def _keeper_aliases(url: str, countries: list[str]) -> tuple[str, str]:
    """From a WhoScored URL find the two nations (home, away) in slug order.

    Matches a pool nation when all of its tokens appear in the URL (so "Congo DR"
    matches ``dr-congo``, "Türkiye" matches ``turkiye``, "Curaçao" matches
    ``curacao``), with an alias table for names that share no full token with the
    slug (e.g. "Korea Republic" ↔ ``south-korea``)."""
    url_tokens = _norm_tokens(url)
    url_set = set(url_tokens)
    flat = " ".join(url_tokens)
    hits = []
    for c in countries:
        ctoks = _norm_tokens(c)
        if not ctoks:
            continue
        cset = set(ctoks)
        alias = _COUNTRY_SLUG_ALIASES.get(" ".join(ctoks), set())
        if cset.issubset(url_set):
            match_toks = cset
        elif alias & url_set:
            match_toks = alias & url_set
        else:
            continue
        pos = min((flat.find(t) for t in match_toks if flat.find(t) >= 0), default=-1)
        if pos >= 0:
            hits.append((pos, c))
    hits.sort()
    home = hits[0][1] if len(hits) >= 1 else None
    away = hits[1][1] if len(hits) >= 2 else None
    return home, away


def is_football_room(room: dict) -> bool:
    return room.get("tournament_type") == "FIFA World Cup 2026"


def match_label(url: str) -> str:
    """Readable 'home-away' label from a WhoScored URL, for progress/error display."""
    tail = url.rstrip("/").split("/")[-1]
    for marker in ("-2026-", "world-cup-"):
        if marker in tail:
            tail = tail.split(marker)[-1]
    return tail or url


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
