"""Event configuration: load tournament player pools and build EngineConfig.

Ports the legacy loaders (``load_players_database`` / ``load_ipl_database`` /
``load_fifa_database``) and normalises every source into ``auction_engine.Player``
objects. Per-event auction rules (timer, budget, squad cap, role categories) are
produced here so the rest of the app never hard-codes tournament specifics.
"""

from __future__ import annotations

import json
import os
import re
from typing import Optional

from auction_engine import EngineConfig, Player

# Tournament identifiers (kept identical to the legacy radio options).
T20_WC = "T20 World Cup"
IPL_2026 = "IPL 2026"
FIFA_WC_2026 = "FIFA World Cup 2026"
UCL_2026 = "UEFA Champions League 2026/27"
TOURNAMENTS = (T20_WC, IPL_2026, FIFA_WC_2026, UCL_2026)

SPORT_BY_TOURNAMENT = {
    T20_WC: "cricket",
    IPL_2026: "cricket",
    FIFA_WC_2026: "football",
    UCL_2026: "football",
}

# Football pools: tournament -> (bundled data file, key holding the team a player
# is bought under). Nations for the World Cup, clubs for a club competition; the
# rest of the football pipeline (keepers-per-team, knockouts, Best-11) is identical.
FOOTBALL_POOLS = {
    FIFA_WC_2026: ("fifa_wc_2026_players.json", "country"),
    UCL_2026: ("ucl_2026_players.json", "team"),
}

# What a player's ``team`` means, for UI wording only — nations at a World Cup,
# clubs in a club competition. The data shape is identical either way.
TEAM_NOUN = {
    FIFA_WC_2026: "country",
    UCL_2026: "club",
}


def team_noun(tournament_type: str, plural: bool = False) -> str:
    noun = TEAM_NOUN.get(tournament_type, "country")
    if not plural:
        return noun
    return "countries" if noun == "country" else noun + "s"


DEFAULT_BUDGET = 100
DEFAULT_TIMER = 60
DEFAULT_MAX_SQUAD = 30

# Free-text role -> composition category (used only if composition is enabled).
CRICKET_ROLE_CATEGORIES = {
    "WK-Batsman": "WK",
    "Wicketkeeper": "WK",
    "Batsman": "BAT",
    "Batting Allrounder": "AR",
    "Bowling Allrounder": "AR",
    "Allrounder": "AR",
    "Bowler": "BWL",
}

# Default data directory = repo root (where the legacy JSON files live).
DATA_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-") or "player"


def _dedupe_ids(players: list[Player]) -> list[Player]:
    seen: dict[str, int] = {}
    for p in players:
        base = p.id
        if base in seen:
            seen[base] += 1
            p.id = f"{base}-{seen[base]}"
        else:
            seen[base] = 0
    return players


# Bundled data files (player pools, schedules) are baked into the image and never
# written at runtime, so reading + parsing them is cached for the process lifetime.
# Before this, every call re-opened and re-parsed the file — and because it ran
# synchronously inside the per-client bidding refresh on the single asyncio worker,
# it blocked the event loop on every poll for every participant. That starved the
# Socket.IO connection (the endless "connecting…" + extreme lag users reported).
_JSON_CACHE: dict = {}
_POOL_CACHE: dict = {}


def _read_json(data_dir: str, filename: str):
    key = (data_dir, filename)
    if key in _JSON_CACHE:
        return _JSON_CACHE[key]
    path = os.path.join(data_dir, filename)
    data = None
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                data = json.load(f)
        except Exception as exc:  # pragma: no cover
            print(f"[config_layer] failed to read {filename}: {exc}")
    _JSON_CACHE[key] = data
    return data


def load_player_pool(tournament_type: str, data_dir: str = DATA_DIR) -> list[Player]:
    """Return the normalised player pool for a tournament (cached; may be empty).

    The built pool is memoised per (tournament, data_dir). Callers get a shallow copy
    so they can't corrupt the cached list; the Player objects are read-only to all
    callers (the auction engine builds its own roster entries separately)."""
    key = (tournament_type, data_dir)
    cached = _POOL_CACHE.get(key)
    if cached is None:
        cached = _build_player_pool(tournament_type, data_dir)
        _POOL_CACHE[key] = cached
    return list(cached)


def _is_keeper(role: str) -> bool:
    r = (role or "").lower()
    return "gk" in r or "keeper" in r


def _build_football_pool(data, team_key: str) -> list[Player]:
    """Normalise a football squad file into the biddable pool.

    Goalkeepers are never bought individually: each team contributes one
    ``"{Team} Keeper"`` entry that scoring aggregates across whoever keeps goal,
    so a team is registered from its keepers even when they are all List B.

    Every other registered player is biddable, UEFA List B (youth) registrations
    included — they are eligible to play, so they are eligible to be bought. The
    ``list_b`` flag is kept on the source rows as provenance.
    """
    rows = data.get("players", []) if isinstance(data, dict) else (data or [])
    players: list[Player] = []
    keeper_teams = set()
    for p in rows:
        if not (isinstance(p, dict) and p.get("name")):
            continue
        team = p.get(team_key) or p.get("team") or p.get("country") or "Unknown"
        role = p.get("role", p.get("position", "Unknown"))
        if _is_keeper(role):
            keeper_teams.add(team)
            continue
        players.append(Player(id=_slug(p["name"]), name=p["name"], team=team,
                              role=role, base_price=p.get("base_price", 0)))
    for team in sorted(keeper_teams):
        name = f"{team} Keeper"
        players.append(Player(id=_slug(name), name=name, team=team,
                              role="Goalkeeper", base_price=0))
    return _dedupe_ids(players)


def _build_player_pool(tournament_type: str, data_dir: str = DATA_DIR) -> list[Player]:
    """Construct the player pool from the bundled data file (uncached)."""
    if tournament_type == IPL_2026:
        data = _read_json(data_dir, "ipl_2026_squads.json") or {}
        players: list[Player] = []
        for code, team in data.get("teams", {}).items():
            team_name = team.get("name", code)
            for p in team.get("squad", []):
                players.append(
                    Player(
                        id=_slug(p["name"]),
                        name=p["name"],
                        team=team_name,
                        role=p.get("role", "Unknown"),
                        base_price=p.get("base_price", 0),
                    )
                )
        return _dedupe_ids(players)

    if tournament_type in FOOTBALL_POOLS:
        filename, team_key = FOOTBALL_POOLS[tournament_type]
        return _build_football_pool(_read_json(data_dir, filename), team_key)

    # Default: T20 World Cup master database.
    data = _read_json(data_dir, "players_database.json") or {}
    players = [
        Player(
            id=_slug(p["name"]),
            name=p["name"],
            team=p.get("country", "Unknown"),
            role=p.get("role", "Unknown"),
            base_price=p.get("base_price", 0),
        )
        for p in data.get("players", [])
    ]
    return _dedupe_ids(players)


def _player_from_row(p: dict) -> Player:
    return Player(id=p.get("id") or _slug(p["name"]), name=p["name"],
                  team=p.get("team", "Unknown"), role=p.get("role", "Unknown"),
                  base_price=p.get("base_price", 0))


def room_player_pool(room: dict) -> list[Player]:
    """Every player biddable in a room — the single source of truth for its pool.

    A room either carries its own uploaded ``player_pool`` or uses the bundled
    pool for its tournament. On top of that sit ``extra_players``: individual
    signings an admin added by CSV, kept separate so adding one player cannot
    replace the pool, and so the room document stays small (a UCL room would
    otherwise carry ~886 rows through every poll).
    """
    if room.get("player_pool"):
        players = [_player_from_row(p) for p in room["player_pool"] if p.get("name")]
    else:
        players = load_player_pool(room.get("tournament_type", "T20 World Cup"))
    extra = room.get("extra_players") or []
    if not extra:
        return players
    have = {p.name.lower() for p in players}
    return players + [_player_from_row(p) for p in extra
                      if p.get("name") and p["name"].lower() not in have]


def load_schedule(tournament_type: str, data_dir: str = DATA_DIR) -> list[dict]:
    """Return the fixture list grouped by gameweek for a tournament (FIFA WC for now).

    Each item: ``{"gw", "name", "matches": [{"teams","date","time","venue"}]}``.
    """
    if tournament_type == FIFA_WC_2026:
        data = _read_json(data_dir, "fifa_wc_2026_schedule.json") or {}
        gws = data.get("gameweeks", {})
        out = []
        for gw, info in sorted(gws.items(), key=lambda kv: (len(kv[0]), kv[0])):
            matches = []
            for m in info.get("matches", []):
                teams = m.get("teams", [])
                matches.append({
                    "teams": " vs ".join(teams) if isinstance(teams, list) else str(teams),
                    "date": m.get("date", ""), "time": m.get("time", ""),
                    "venue": m.get("venue", ""),
                })
            out.append({"gw": str(gw), "name": info.get("name", f"Gameweek {gw}"),
                        "matches": matches})
        return out
    return []


def default_config(
    tournament_type: str,
    budget: int = DEFAULT_BUDGET,
    enforce_composition: bool = False,
) -> EngineConfig:
    """Build the default auction rules for a tournament.

    ``enforce_composition`` is False by default to match legacy cricket behaviour
    (role limits were only ever applied at Best-11 scoring, not at buy time).
    """
    sport = SPORT_BY_TOURNAMENT.get(tournament_type, "cricket")
    role_categories = CRICKET_ROLE_CATEGORIES if sport == "cricket" else {}
    composition: dict[str, tuple[int, int]] = {}
    if enforce_composition and sport == "cricket":
        # Mirrors the current Best-11 ranges; enable only if an event opts in.
        composition = {"WK": (1, 3), "BAT": (1, 6), "AR": (2, 6), "BWL": (3, 6)}
    return EngineConfig(
        timer_seconds=DEFAULT_TIMER,
        starting_min_bid=5,
        max_squad=DEFAULT_MAX_SQUAD,
        composition=composition,
        role_categories=role_categories,
    )
