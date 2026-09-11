"""Automated gameweek scoring from WhoScored match links.

Given the WhoScored links for a gameweek's matches, scrape each, compute per-player
fantasy points, and aggregate into ``room['gameweek_scores'][gw]``. Standings then
award points off each participant's *locked* squad for that gameweek (IR excluded).
This is the "automation" — the admin supplies the gameweek's match links and the
points are computed and stored in one action.
"""

from __future__ import annotations

import re


def parse_links(text: str) -> list[str]:
    out = []
    for line in (text or "").splitlines():
        line = line.strip()
        if line.startswith("http"):
            out.append(line)
    return out


# Firebase Realtime Database rejects these characters in a KEY, and the whole
# document is written in one PUT — so a single bad key fails the entire save with
# a 400, losing every other change in it. Gameweek scores are keyed by player
# name, and UEFA's club short names put illegal characters into the per-club
# keeper entries: "B. Dortmund Keeper", "S. Bratislava Keeper", "Bodø/Glimt
# Keeper" (that "/" would also read back as a path separator), plus players like
# "Jerry St. Juste". The World Cup pool happened to contain none, which is why
# this only appears with a club competition.
_ILLEGAL_KEY_CHARS = re.compile(r"[.$#\[\]/]")


def safe_score_key(name: str) -> str:
    """A player name usable as a Firebase key.

    Illegal characters become spaces. Nothing is lost: scores are looked up
    through ``season_engine.names`` on a canonical form that already ignores
    punctuation and how a name is split, so "B Dortmund Keeper" still resolves
    from a squad holding "B. Dortmund Keeper".
    """
    return " ".join(_ILLEGAL_KEY_CHARS.sub(" ", str(name or "")).split())


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
    from platform_core.config_layer import room_player_pool
    return sorted({p.team for p in room_player_pool(room) if p.name.endswith(" Keeper")})


def _norm_tokens(s: str) -> list[str]:
    """Lowercase, accent-stripped tokens split on any non-alphanumeric run — so a
    URL slug and a nation name tokenise the same way (hyphens are separators here,
    unlike player-name canonicalisation which joins across them)."""
    import re
    import unicodedata
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = "".join(c for c in s if not unicodedata.combining(c)).casefold()
    return [t for t in re.split(r"[^a-z0-9]+", s) if t]


# Pool team names that share no full token with their WhoScored URL slug — map the
# token form of the pool name to the distinctive slug token(s). Nations come from
# the World Cup pool, clubs from the UEFA pools (UEFA's short display names differ
# from WhoScored's, e.g. "Atleti" vs atletico-madrid). Each alias must be a token
# that no OTHER team in the same pool can claim, since a match URL names two teams.
_TEAM_SLUG_ALIASES = {
    # FIFA World Cup nations
    "korea republic": {"korea"},          # url: ...-south-korea-...
    "ir iran": {"iran"},                  # url: ...-iran-...
    "cote d ivoire": {"ivory", "coast"},  # url: ...-ivory-coast-...
    # UEFA Champions League clubs
    "atleti": {"atletico"},               # url: ...-atletico-madrid-...
    "b dortmund": {"dortmund"},           # url: ...-borussia-dortmund-...
    "bayern munchen": {"bayern"},         # url: ...-bayern-munich-...
    "bod glimt": {"glimt"},               # "Bodø/Glimt" keeps no ascii token of "bodo"
    "inter": {"internazionale"},          # url: ...-internazionale-...
    "man city": {"city"},                 # url: ...-manchester-city-...
    "man utd": {"united"},                # url: ...-manchester-united-...
    "s bratislava": {"bratislava"},       # url: ...-slovan-bratislava-...
    "slavia praha": {"slavia"},           # url: ...-slavia-prague-...
    "sporting cp": {"sporting"},          # url: ...-sporting-lisbon-...
}


def _seq_index(tokens: list[str], seq: list[str], taken: set[int]) -> int:
    """Index of the first unclaimed contiguous run of ``seq`` in ``tokens`` (-1 if none)."""
    n = len(seq)
    for i in range(len(tokens) - n + 1):
        if tokens[i:i + n] == seq and not (taken & set(range(i, i + n))):
            return i
    return -1


def _keeper_aliases(url: str, countries: list[str]) -> tuple[str, str]:
    """From a WhoScored URL find the two teams (home, away) in slug order.

    Teams are resolved GREEDILY, most-certain first, and each URL token can be
    claimed by only one team. That matters because pool names overlap: without it
    ``atletico-madrid-real-betis`` lets "Real Madrid" borrow *madrid* from Atleti
    and *real* from Betis and match a club that isn't playing, and
    ``villarreal-aston-villa`` can't tell which side is home.

      1. the team's own name as an unbroken, in-order run of tokens;
      2. an explicit alias, where WhoScored spells the team differently
         ("Atleti" ↔ atletico-madrid, "Bodø/Glimt" ↔ bodoe-glimt);
      3. all of its tokens present but out of order ("Congo DR" ↔ dr-congo),
         over whatever tokens nobody has claimed.

    Home/away come from TOKEN position, not string offset — "villa" appears inside
    "villarreal" but is a different token.
    """
    url_tokens = _norm_tokens(url)
    pending = [(c, _norm_tokens(c)) for c in countries]
    pending = [(c, toks) for c, toks in pending if toks]
    taken: set[int] = set()
    hits: dict[str, int] = {}

    # 1. Exact name runs. Longest names first, so a short name can't steal a token
    #    that belongs to a longer one.
    for c, toks in sorted(pending, key=lambda x: -len(x[1])):
        i = _seq_index(url_tokens, toks, taken)
        if i >= 0:
            hits[c] = i
            taken |= set(range(i, i + len(toks)))

    # 2. Aliases, over tokens no team has claimed.
    for c, toks in pending:
        if c in hits:
            continue
        alias = _TEAM_SLUG_ALIASES.get(" ".join(toks), set())
        free = [i for i, tok in enumerate(url_tokens) if tok in alias and i not in taken]
        if free:
            hits[c] = free[0]
            taken.add(free[0])

    # 3. Out-of-order names, again only over unclaimed tokens.
    for c, toks in pending:
        if c in hits:
            continue
        want = set(toks)
        free = {i: tok for i, tok in enumerate(url_tokens) if i not in taken}
        if want <= set(free.values()):
            matched = {i for i, tok in free.items() if tok in want}
            hits[c] = min(matched)
            taken |= matched

    ordered = [c for c, _ in sorted(hits.items(), key=lambda kv: kv[1])]
    home = ordered[0] if ordered else None
    away = ordered[1] if len(ordered) > 1 else None
    return home, away


def is_football_room(room: dict) -> bool:
    from platform_core.config_layer import SPORT_BY_TOURNAMENT
    return SPORT_BY_TOURNAMENT.get(room.get("tournament_type", ""), "cricket") == "football"


def match_label(url: str) -> str:
    """Readable 'home-away' label from a WhoScored URL, for progress/error display."""
    tail = url.rstrip("/").split("/")[-1]
    for marker in ("-2026-", "world-cup-", "champions-league-"):
        if marker in tail:
            tail = tail.split(marker)[-1]
    return tail or url


def fifa_countries(room: dict) -> list[str]:
    """Public wrapper: distinct nations with a 'Keeper' entry in this room."""
    return _fifa_countries(room)


def registered_positions(room: dict) -> dict:
    """``{player name: role}`` from the room's OWN pool.

    This decides which formula scores each player, so it must come from the
    competition being scored. The scorer's fallback is the World Cup squad file,
    which for a UCL room knows almost nobody and quietly scored 715 of 945
    players on whatever position WhoScored recorded them playing.
    """
    from .config_layer import room_player_pool
    return {p.name: p.role for p in room_player_pool(room)}


def score_one_link(url: str, *, is_football: bool, countries: list[str],
                   positions: dict | None = None) -> dict:
    """Scrape ONE match link → ``{player_or_keeper_name: number | {pos: score}}``.

    Pure per-match scrape with no room mutation, so a caller can loop over the
    gameweek's links one at a time and report progress between matches.
    """
    from scoring import whoscored_keeper_scores, whoscored_player_scores

    out: dict = {}
    for name, sc in whoscored_player_scores(url, positions).items():
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
    """Fold one match's ``score_one_link`` result into the running gameweek totals.

    Keys are made Firebase-safe here, at the one point every scoring path funnels
    through, so the stored gameweek can always be written back."""
    for name, sc in one.items():
        key = safe_score_key(name)
        totals[key] = _merge(totals.get(key), sc)


def score_gameweek_from_links(room: dict, gameweek: str, links: list[str]) -> tuple[dict, list[str]]:
    """Scrape each link, store per-player points (dual-position aware) under the
    gameweek. For football, each nation's goalkeeper points are stored under
    ``"{Country} Keeper"`` (keepers are owned per nation). Best-11 picks each
    player's best position from the ``{pos: score}`` dicts.
    """
    is_football = is_football_room(room)
    countries = fifa_countries(room) if is_football else []
    positions = registered_positions(room) if is_football else None
    totals: dict = {}
    errors: list[str] = []
    for url in links:
        try:
            merge_link_totals(totals, score_one_link(
                url, is_football=is_football, countries=countries, positions=positions))
        except Exception as exc:  # network / bot-block / parse
            errors.append(f"{url[:60]}…: {exc}")
    if totals:
        room.setdefault("gameweek_scores", {})[str(gameweek)] = totals
    return totals, errors
