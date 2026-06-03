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
TOURNAMENTS = (T20_WC, IPL_2026, FIFA_WC_2026)

SPORT_BY_TOURNAMENT = {
    T20_WC: "cricket",
    IPL_2026: "cricket",
    FIFA_WC_2026: "football",
}

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


def _read_json(data_dir: str, filename: str):
    path = os.path.join(data_dir, filename)
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception as exc:  # pragma: no cover
            print(f"[config_layer] failed to read {filename}: {exc}")
    return None


def load_player_pool(tournament_type: str, data_dir: str = DATA_DIR) -> list[Player]:
    """Return the normalised player pool for a tournament (may be empty)."""
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

    if tournament_type == FIFA_WC_2026:
        data = _read_json(data_dir, "fifa_wc_2026_players.json") or []
        players = [
            Player(
                id=_slug(p["name"]),
                name=p["name"],
                team=p.get("country", p.get("team", "Unknown")),
                role=p.get("role", p.get("position", "Unknown")),
                base_price=p.get("base_price", 0),
            )
            for p in data
            if isinstance(p, dict) and p.get("name")
        ]
        return _dedupe_ids(players)

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
