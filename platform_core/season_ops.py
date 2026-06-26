"""Season operations over the room document (gameweek lifecycle + standings).

Bridges the room schema (``participants``, ``gameweek_scores``, ``gameweek_squads``)
to the pure ``season_engine`` algorithms. Pure dict operations — persistence is the
caller's job.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta

from season_engine.knockout import select_for_elimination
from season_engine.names import build_index, lookup
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


def _participants_for_gameweek(room: dict, gameweek: str) -> list[dict]:
    """Participants with the LOCKED squad snapshot for ``gameweek`` when one
    exists (so points always come from locked squads, never the live ones);
    falls back to the current squad only for gameweeks that were never locked."""
    snap = room.get("gameweek_squads", {}).get(str(gameweek))
    out = []
    for p in _participants_for_standings(room):
        team_snap = (snap or {}).get(p["name"])
        if isinstance(team_snap, dict):
            squad = team_snap.get("squad") or []
            out.append({"name": p["name"],
                        "squad": [{"name": s["name"], "role": s.get("role", "")} for s in squad],
                        "ir": team_snap.get("ir")})
        elif isinstance(team_snap, list):   # legacy snapshot shape
            out.append({"name": p["name"],
                        "squad": [{"name": s["name"], "role": s.get("role", "")} for s in team_snap],
                        "ir": p.get("ir")})
        else:
            out.append(p)
    return out


def compute_gameweek_standings(room: dict, gameweek: str) -> list[dict]:
    # enforce_ir=False = owner rule: the IR only binds for a FULL (>= 19) squad;
    # below that the IR player still counts in Best-11.
    scores = room.get("gameweek_scores", {}).get(str(gameweek), {})
    return gameweek_standings(
        _participants_for_gameweek(room, gameweek), scores,
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
    that gameweek are FREE (no money back). Players from a nation the admin marked
    as knocked out always refund half price WITHOUT consuming the paid-release
    allowance. Returns the refund."""
    by = {p["name"]: p for p in room.get("participants", [])}
    p = by.get(participant)
    if p is None:
        raise SeasonError("Unknown team.")
    e = next((x for x in p.get("squad", []) if x["name"].lower() == player_name.lower()), None)
    if e is None:
        raise SeasonError(f"You don't own {player_name}.")
    if e.get("acquired_via") == "loan":
        raise SeasonError(f"{player_name} is on loan to you — you can't release them.")

    ko = (e.get("team") or "") in set(knocked_out_countries(room))
    if ko:
        refund = math.ceil(e.get("buy_price", 0) / 2)  # KO release: half, no allowance used
    elif not room.get("gw1_locked"):
        refund = math.ceil(e.get("buy_price", 0) / 2)  # unlimited half-price pre-GW1
    elif p.get("half_releases_this_gw", 0) < 1:
        refund = math.ceil(e.get("buy_price", 0) / 2)  # one half-price per GW
        p["half_releases_this_gw"] = p.get("half_releases_this_gw", 0) + 1
    else:
        refund = 0                                    # further releases are free

    p["squad"].remove(e)
    p["budget"] = p.get("budget", 0) + refund
    room.setdefault("transactions", []).append(
        {"ts": datetime.now().isoformat(), "type": "half_release", "participant": participant,
         "player": player_name, "refund": refund, "buy_price": e.get("buy_price", 0),
         "role": e.get("role", ""), "player_team": e.get("team", ""), "ko": ko})
    return refund


# --- knocked-out nations --------------------------------------------------- #
def knocked_out_countries(room: dict) -> list[str]:
    return list(room.get("knocked_out_countries", []) or [])


def mark_country_knocked_out(room: dict, country: str, knocked: bool = True) -> list[str]:
    """Admin marks a nation as knocked out of the tournament (or undoes it).

    While knocked out: players of that nation can't receive open bids (any
    standing open bids on them are cancelled here), and owners may release them
    at half price without using their paid release for the gameweek.
    Returns the names of players whose open bids were cancelled."""
    country = (country or "").strip()
    if not country:
        raise SeasonError("Pick a country.")
    cur = room.setdefault("knocked_out_countries", [])
    cancelled: list[str] = []
    if knocked:
        if country not in cur:
            cur.append(country)
        ob = room.get("open_bids", {}) or {}
        for name in [n for n, b in ob.items() if (b.get("team") or "") == country]:
            del ob[name]
            cancelled.append(name)
        # Also drop sealed market bids on this nation's players.
        from . import bidding_ops as bo
        nation_players = {p["name"].lower() for p in bo._pool(room)
                          if (p.get("team") or "") == country}
        room["active_bids"] = [b for b in room.get("active_bids", [])
                               if (b.get("player") or "").lower() not in nation_players]
    elif country in cur:
        cur.remove(country)
    return cancelled


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
        released, notes = lock_participant(p)
        if notes:
            notes_all[p["name"]] = notes
        # Log auto-releases (squad-cap trim / unaffordable IR) so they show in the
        # announcements feed and can be reversed by the admin if needed.
        for e in released:
            room.setdefault("transactions", []).append({
                "ts": datetime.now().isoformat(), "type": "half_release",
                "participant": p["name"], "player": e.get("name", "?"), "refund": 0,
                "buy_price": e.get("buy_price", 0), "role": e.get("role", ""),
                "player_team": e.get("team", ""), "auto": True,
                "reason": "auto-released at squad lock",
            })
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

    # Any trade still unresolved at lock (not yet accepted, or accepted but not
    # admin-approved) dies with the gameweek — auto-rejected, never applied.
    for t in room.get("pending_trades", []):
        if t.get("status") in ("pending", "awaiting_admin"):
            t["status"] = "auto_rejected"

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
    new_gw = cur + 1
    room["current_gameweek"] = new_gw
    
    # Auto-return expired loans
    loans = room.get("active_loans", [])
    returned = []
    for l in loans:
        try:
            if int(l.get("return_gameweek", 999)) <= new_gw:
                returned.append(l)
        except (ValueError, TypeError):
            pass
            
    if returned:
        by = {p["name"]: p for p in room.get("participants", [])}
        for loan in returned:
            to_team = by.get(loan["to"])
            from_team = by.get(loan["from"])
            if to_team:
                cur_p = next((p for p in to_team.get("squad", []) if (p.get("name") if isinstance(p, dict) else p) == loan["player"]), None)
                if cur_p is not None:
                    to_team["squad"].remove(cur_p)
            if from_team:
                returned_entry = dict(loan["entry"])
                # Defensive: the returning player is owned outright again — never
                # leave them flagged on-loan (older loan records snapshotted the
                # entry after it was marked, so normalise here too).
                if returned_entry.get("acquired_via") == "loan":
                    returned_entry["acquired_via"] = "trade"
                from_team.setdefault("squad", []).append(returned_entry)
            loans.remove(loan)
            
    return new_gw


# --- top player scorers -------------------------------------------------- #
def _player_point_totals(room: dict, gameweek: str | None = None) -> dict[str, int]:
    """Points per *player* — for a single ``gameweek`` (str) or cumulative across all
    gameweeks (``gameweek=None``). Dual-position scores count the player's best slot."""
    gw_scores = room.get("gameweek_scores", {})
    if gameweek is None:
        sources = gw_scores.values()
    else:
        sources = [gw_scores.get(str(gameweek), {})]
    totals: dict[str, int] = {}
    for scores in sources:
        for player, pts in scores.items():
            if isinstance(pts, dict):     # dual-position: count their best position
                pts = max(pts.values()) if pts else 0
            try:
                totals[player] = totals.get(player, 0) + int(pts)
            except (TypeError, ValueError):
                pass
    return totals


def _player_owner_index(room: dict):
    owner = {}
    for p in room.get("participants", []):
        for e in p.get("squad", []):
            owner[e["name"]] = p["name"]
    return build_index(owner)


def _player_country_index(room: dict):
    """Fuzzy name → country index. A player's squad ``team`` field is their country
    for football (the franchise for cricket), the same field the squad sort uses."""
    country = {}
    for p in room.get("participants", []):
        for e in p.get("squad", []):
            if e.get("team"):
                country[e["name"]] = e["team"]
    return build_index(country)


def top_player_scorers(room: dict, limit: int = 25) -> list[dict]:
    """Cumulative points per *player* across all gameweeks, with current owner."""
    owner_index = _player_owner_index(room)
    country_index = _player_country_index(room)
    rows = [{"player": n, "points": t, "owner": lookup(owner_index, n, "—"),
             "country": lookup(country_index, n, "—")}
            for n, t in _player_point_totals(room).items()]
    rows.sort(key=lambda r: r["points"], reverse=True)
    return rows[:limit]


def search_player_points(room: dict, query: str = "", gameweek: str | None = None,
                         limit: int = 50) -> list[dict]:
    """Points per player for a single ``gameweek`` (str) or cumulative (``None``),
    filtered by a case-insensitive substring of the player's name and sorted high→low.
    Each row carries the player's country and current owner."""
    owner_index = _player_owner_index(room)
    country_index = _player_country_index(room)
    q = (query or "").strip().lower()
    rows = [{"player": n, "points": t, "owner": lookup(owner_index, n, "—"),
             "country": lookup(country_index, n, "—")}
            for n, t in _player_point_totals(room, gameweek).items()
            if not q or q in n.lower()]
    rows.sort(key=lambda r: r["points"], reverse=True)
    return rows[:limit]


# --- gameweek deadlines + automation ------------------------------------- #
# Trading stays open until T + this many minutes; at T+30m squads lock, the gameweek
# advances and the market freezes. Single source of truth (used here and by the
# deadline push scheduler).
TRADING_LOCK_MIN = 30


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
    return now < dl + timedelta(minutes=TRADING_LOCK_MIN)


def deadline_work_due(room: dict, now: datetime) -> bool:
    """Cheap check: does this room have bidding-deadline work pending right now?
    (Awards at the deadline, or the +30m lock/advance/freeze.) Used by the
    per-page live loops so the timeline still fires when the scheduler thread
    is disabled — any connected client drives it."""
    from . import bidding_ops as bo
    dl = bo.bidding_deadline(room)
    if dl is None:
        return False
    if now >= dl and not room.get("bids_resolved"):
        return True
    return now >= dl + timedelta(minutes=TRADING_LOCK_MIN) and not room.get("locked_for_deadline")


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
    if now >= dl + timedelta(minutes=TRADING_LOCK_MIN) and not room.get("locked_for_deadline"):
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
            if dt.tzinfo is not None:
                dt = dt.astimezone().replace(tzinfo=None)
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
