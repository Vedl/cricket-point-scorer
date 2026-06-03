"""Season operations over the room document (gameweek lifecycle + standings).

Bridges the room schema (``participants``, ``gameweek_scores``, ``gameweek_squads``)
to the pure ``season_engine`` algorithms. Pure dict operations — persistence is the
caller's job.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from season_engine.knockout import select_for_elimination
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
        is_football=_is_football(room), gameweek=gameweek, enforce_ir=False,
    )


def compute_cumulative_standings(room: dict) -> list[dict]:
    all_scores = {str(k): v for k, v in room.get("gameweek_scores", {}).items()}
    squads_by_gw = room.get("gameweek_squads") or None
    return cumulative_standings(
        _participants_for_standings(room), all_scores,
        is_football=_is_football(room), squads_by_gw=squads_by_gw, enforce_ir=False,
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


GW1_BOOST = 100


class SeasonError(Exception):
    """A season action failed (message is user-facing)."""


def set_ir(room: dict, participant: str, player_name) -> None:
    """A participant nominates their Injury Reserve player (or None to clear)."""
    by = {p["name"]: p for p in room.get("participants", [])}
    p = by.get(participant)
    if p is None:
        raise SeasonError("Unknown team.")
    if player_name and not any(e["name"] == player_name for e in p.get("squad", [])):
        raise SeasonError("That player isn't in your squad.")
    p["ir"] = player_name or None


def half_price_release(room: dict, participant: str, player_name: str) -> int:
    """Release a player. Before the GW1 deadline: unlimited half-price refunds.
    After GW1: the first release each gameweek is half-price; any further releases
    that gameweek are FREE (no money back). Returns the refund."""
    by = {p["name"]: p for p in room.get("participants", [])}
    p = by.get(participant)
    if p is None:
        raise SeasonError("Unknown team.")
    e = next((x for x in p.get("squad", []) if x["name"].lower() == player_name.lower()), None)
    if e is None:
        raise SeasonError(f"You don't own {player_name}.")

    if not room.get("gw1_locked"):
        refund = e.get("buy_price", 0) // 2          # unlimited half-price pre-GW1
    elif p.get("half_releases_this_gw", 0) < 1:
        refund = e.get("buy_price", 0) // 2          # one half-price per GW
        p["half_releases_this_gw"] = p.get("half_releases_this_gw", 0) + 1
    else:
        refund = 0                                    # further releases are free

    p["squad"].remove(e)
    p["budget"] = p.get("budget", 0) + refund
    room.setdefault("transactions", []).append(
        {"type": "half_release", "participant": participant, "player": player_name, "refund": refund})
    return refund


def lock_gameweek(room: dict, gameweek: str) -> tuple[dict, bool]:
    """Lock squads for a gameweek: apply the IR + 19-cap pipeline per participant,
    snapshot the squads, freeze the market, and (on the first ever lock) grant the
    +100M boost. Returns ``(per_participant_notes, was_first_lock)``.
    """
    from season_engine.squad_lock import lock_participant

    notes_all: dict[str, list[str]] = {}
    for p in room.get("participants", []):
        if p.get("is_eliminated"):
            continue
        _released, notes = lock_participant(p)
        if notes:
            notes_all[p["name"]] = notes
        p["half_releases_this_gw"] = 0  # reset allowance for the new gameweek

    # Snapshot AFTER the pipeline so scoring uses the locked squads + IR.
    snap = {}
    for p in room.get("participants", []):
        snap[p["name"]] = {
            "squad": [{"name": s["name"], "role": s.get("role", "")} for s in p.get("squad", [])],
            "ir": p.get("ir"),
        }
    room.setdefault("gameweek_squads", {})[str(gameweek)] = snap
    room["bidding_open"] = False
    room["trading_open"] = False

    first = not room.get("gw1_locked")
    if first:
        room["gw1_locked"] = True
        for p in room.get("participants", []):
            p["budget"] = p.get("budget", 0) + GW1_BOOST
    room["locked_gameweek"] = str(gameweek)
    return notes_all, first


# Backwards-compatible alias (simple callers).
def lock_squads_for_gameweek(room: dict, gameweek: str) -> None:
    lock_gameweek(room, gameweek)


def advance_gameweek(room: dict) -> int:
    cur = int(room.get("current_gameweek", 0) or 0)
    room["current_gameweek"] = cur + 1
    return room["current_gameweek"]


# --- top player scorers -------------------------------------------------- #
def top_player_scorers(room: dict, limit: int = 25) -> list[dict]:
    """Cumulative points per *player* across all gameweeks, with current owner."""
    totals: dict[str, int] = {}
    for scores in room.get("gameweek_scores", {}).values():
        for player, pts in scores.items():
            try:
                totals[player] = totals.get(player, 0) + int(pts)
            except (TypeError, ValueError):
                pass
    owner = {}
    for p in room.get("participants", []):
        for e in p.get("squad", []):
            owner[e["name"].lower()] = p["name"]
    rows = [{"player": n, "points": t, "owner": owner.get(n.lower(), "—")}
            for n, t in totals.items()]
    rows.sort(key=lambda r: r["points"], reverse=True)
    return rows[:limit]


# --- gameweek deadlines + automation ------------------------------------- #
def set_deadline(room: dict, gameweek: str, iso: str) -> None:
    room.setdefault("gameweek_deadlines", {})[str(gameweek)] = iso


def deadlines(room: dict) -> dict:
    return room.get("gameweek_deadlines", {})


def set_bidding_deadline(room: dict, iso: str) -> None:
    """Admin sets the bidding deadline for the current gameweek; un-freezes the market."""
    room["bidding_deadline"] = iso
    room["bids_resolved"] = False
    room["locked_for_deadline"] = False
    room["bidding_open"] = True
    room["trading_open"] = True
    if int(room.get("current_gameweek", 0) or 0) < 1:
        room["current_gameweek"] = 1


def trading_open(room: dict, now: datetime) -> bool:
    """Trading is allowed until the trading deadline (bidding deadline + 30m)."""
    from . import bidding_ops as bo
    dl = bo.bidding_deadline(room)
    if dl is None:
        return False
    return now < dl + timedelta(minutes=30)


def process_room_deadline(room: dict, now: datetime) -> list[str]:
    """Drive the bidding/trading/lock timeline from the single bidding deadline.

    At the deadline: award all standing bids. At deadline+30m: lock squads,
    advance the gameweek, and freeze bidding+trading until the admin sets a new
    deadline. Returns a list of human-readable events that happened.
    """
    from . import bidding_ops as bo
    dl = bo.bidding_deadline(room)
    if dl is None:
        return []
    events: list[str] = []
    awarded = bo.resolve_deadline(room, now)
    if awarded:
        events.append(f"awarded {len(awarded)} open bids")
    if now >= dl + timedelta(minutes=30) and not room.get("locked_for_deadline"):
        gw = str(int(room.get("current_gameweek", 1) or 1))
        lock_gameweek(room, gw)
        advance_gameweek(room)
        room["locked_for_deadline"] = True
        room["bidding_open"] = False
        room["trading_open"] = False
        room["bidding_deadline"] = None      # frozen until admin sets the next one
        room["bids_resolved"] = False
        events.append(f"locked GW{gw}, started the next gameweek, froze the market")
    return events


def process_due_deadlines(room: dict, now: datetime) -> list[str]:
    """Auto-lock + advance any gameweek whose deadline has passed and which hasn't
    been locked yet. Returns the gameweeks processed."""
    processed: list[str] = []
    locked = room.get("gameweek_squads", {})
    for gw, iso in sorted(room.get("gameweek_deadlines", {}).items()):
        if gw in locked:
            continue
        try:
            dt = datetime.fromisoformat(iso)
        except (ValueError, TypeError):
            continue
        if now >= dt:
            lock_gameweek(room, gw)
            advance_gameweek(room)
            processed.append(gw)
    return processed


# --- knockout ------------------------------------------------------------ #
def eliminated_names(room: dict) -> set[str]:
    return {p["name"] for p in room.get("participants", []) if p.get("is_eliminated")}


def eliminate_for_gameweek(room: dict, gameweek: str, count: int = 1) -> list[str]:
    """Eliminate the bottom ``count`` active participants by that gameweek's Best-11."""
    standings = compute_gameweek_standings(room, gameweek)
    losers = select_for_elimination(
        standings, count=count, already_eliminated=eliminated_names(room)
    )
    by = {p["name"]: p for p in room.get("participants", [])}
    for name in losers:
        if name in by:
            by[name]["is_eliminated"] = True
    if losers:
        room.setdefault("knockout_history", []).append(
            {"gameweek": str(gameweek), "eliminated": losers}
        )
    return losers


# Standard FIFA-style knockout cutoffs: round name -> teams kept after it.
KNOCKOUT_ROUNDS = [
    ("Round of 16", 8),
    ("Quarter-final", 4),
    ("Semi-final", 2),
    ("Final", 1),
]


def eliminate_below_position(room: dict, gameweek: str, keep_top: int) -> tuple[list[str], list[str]]:
    """Keep the top ``keep_top`` active teams for a gameweek; eliminate the rest.

    Eliminated teams' players are released into the open-market pool so survivors
    can bid on them in the next round (the FIFA WC knockout flow). Reversible.
    Returns ``(eliminated_names, released_player_names)``.
    """
    standings = compute_gameweek_standings(room, gameweek)
    already = eliminated_names(room)
    active = [r for r in standings if r["participant"] not in already]
    if len(active) <= keep_top:
        return [], []

    losers = [r["participant"] for r in active[keep_top:]]
    by = {p["name"]: p for p in room.get("participants", [])}
    pool = room.setdefault("unsold_players", [])
    pool_names = {(p.get("name") if isinstance(p, dict) else p) for p in pool}

    entries = []
    released: list[str] = []
    for name in losers:
        p = by.get(name)
        if not p:
            continue
        # Snapshot the squad so the round can be reversed.
        squad_snapshot = [dict(e) for e in p.get("squad", [])]
        entries.append({"name": name, "squad": squad_snapshot})
        p["is_eliminated"] = True
        for e in squad_snapshot:
            if e["name"] not in pool_names:
                pool.append({"name": e["name"], "role": e.get("role", ""), "team": e.get("team", "")})
                pool_names.add(e["name"])
                released.append(e["name"])
        p["squad"] = []  # players are now free agents

    room.setdefault("knockout_history", []).append({
        "gameweek": str(gameweek), "keep_top": keep_top,
        "eliminated": losers, "entries": entries, "released": released,
    })
    return losers, released


def reverse_last_elimination(room: dict) -> list[str]:
    """Undo the most recent knockout round.

    Un-eliminates the teams, restores any released squads, and removes the
    released players from the market pool.
    """
    history = room.get("knockout_history", [])
    if not history:
        return []
    last = history.pop()
    by = {p["name"]: p for p in room.get("participants", [])}
    for name in last["eliminated"]:
        if name in by:
            by[name]["is_eliminated"] = False
    # Restore squads (position-cutoff rounds snapshot them).
    for entry in last.get("entries", []):
        if entry["name"] in by:
            by[entry["name"]]["squad"] = entry["squad"]
    # Remove the released players from the market pool.
    released = set(last.get("released", []))
    if released:
        room["unsold_players"] = [
            p for p in room.get("unsold_players", [])
            if (p.get("name") if isinstance(p, dict) else p) not in released
        ]
    return last["eliminated"]
