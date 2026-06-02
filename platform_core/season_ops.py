"""Season operations over the room document (gameweek lifecycle + standings).

Bridges the room schema (``participants``, ``gameweek_scores``, ``gameweek_squads``)
to the pure ``season_engine`` algorithms. Pure dict operations — persistence is the
caller's job.
"""

from __future__ import annotations

from season_engine.standings import cumulative_standings, gameweek_standings

from .config_layer import SPORT_BY_TOURNAMENT


def _is_football(room: dict) -> bool:
    return SPORT_BY_TOURNAMENT.get(room.get("tournament_type", ""), "cricket") == "football"


def _participants_for_standings(room: dict) -> list[dict]:
    out = []
    for p in room.get("participants", []):
        out.append(
            {
                "name": p["name"],
                "squad": [{"name": s["name"], "role": s.get("role", "")} for s in p.get("squad", [])],
                "ir": p.get("ir"),
            }
        )
    return out


def compute_gameweek_standings(room: dict, gameweek: str) -> list[dict]:
    scores = room.get("gameweek_scores", {}).get(str(gameweek), {})
    return gameweek_standings(
        _participants_for_standings(room), scores,
        is_football=_is_football(room), gameweek=gameweek,
    )


def compute_cumulative_standings(room: dict) -> list[dict]:
    all_scores = {str(k): v for k, v in room.get("gameweek_scores", {}).items()}
    squads_by_gw = room.get("gameweek_squads") or None
    return cumulative_standings(
        _participants_for_standings(room), all_scores,
        is_football=_is_football(room), squads_by_gw=squads_by_gw,
    )


def gameweeks_with_scores(room: dict) -> list[str]:
    return sorted(room.get("gameweek_scores", {}).keys(), key=lambda g: (len(g), g))


# --- lifecycle ----------------------------------------------------------- #
def set_gameweek_scores(room: dict, gameweek: str, scores: dict[str, int]) -> None:
    room.setdefault("gameweek_scores", {})[str(gameweek)] = scores


def parse_scores_text(text: str) -> tuple[dict[str, int], list[str]]:
    """Parse 'Player Name, score' lines into a score dict. Returns (scores, errors)."""
    scores: dict[str, int] = {}
    errors: list[str] = []
    for i, line in enumerate(text.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        if "," not in line:
            errors.append(f"Line {i}: expected 'Player, score'.")
            continue
        name, _, val = line.rpartition(",")
        name = name.strip()
        try:
            scores[name] = int(round(float(val.strip())))
        except ValueError:
            errors.append(f"Line {i}: '{val.strip()}' is not a number.")
    return scores, errors


def lock_squads_for_gameweek(room: dict, gameweek: str) -> None:
    """Snapshot every participant's current squad for a gameweek (freeze for scoring)."""
    snap = {}
    for p in room.get("participants", []):
        snap[p["name"]] = {
            "squad": [{"name": s["name"], "role": s.get("role", "")} for s in p.get("squad", [])],
            "ir": p.get("ir"),
        }
    room.setdefault("gameweek_squads", {})[str(gameweek)] = snap
    room["bidding_open"] = False
    room["trading_open"] = False


def advance_gameweek(room: dict) -> int:
    cur = int(room.get("current_gameweek", 0) or 0)
    room["current_gameweek"] = cur + 1
    return room["current_gameweek"]
