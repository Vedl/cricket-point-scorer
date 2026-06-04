"""Repository: the seam between the engines and the Firebase document.

Maps the auction engine's objects to/from the legacy room schema
(``rooms/{code}`` with ``participants``, ``live_auction``/``auction_state`` etc.)
and provides the room/participant operations the Reflex layer calls.

Pure mapping helpers are module-level (unit-tested without any store); the
``Repository`` class binds them to a :class:`FirebaseStore`.
"""

from __future__ import annotations

import random
import string
from datetime import datetime, timezone
from typing import Optional

from auction_engine import AuctionEngine, AuctionState, BidLogEntry, Participant, RosterEntry

from .config_layer import (
    DEFAULT_BUDGET,
    default_config,
    load_player_pool,
)
from .config_layer import _slug  # reuse the canonical id slugger
from .csv_import import ParseResult
from .firebase_store import FirebaseStore


class RepositoryError(Exception):
    """User-facing repository operation failure."""


# --------------------------------------------------------------------------- #
# Participant <-> room mapping
# --------------------------------------------------------------------------- #
def participant_from_room(p: dict) -> Participant:
    """Build an engine Participant from a legacy room participant dict."""
    squad = []
    for e in p.get("squad", []):
        squad.append(
            RosterEntry(
                player_id=_slug(e["name"]),
                name=e["name"],
                role=e.get("role", "Unknown"),
                team=e.get("team", "Unknown"),
                price_paid=e.get("buy_price", e.get("price_paid", 0)),
                acquired_via=e.get("acquired_via", "auction"),
            )
        )
    return Participant(
        id=p["name"],            # names are unique within a room (legacy invariant)
        name=p["name"],
        budget=p.get("budget", DEFAULT_BUDGET),
        squad=squad,
    )


def participant_to_room(p: Participant, *, user: Optional[str] = None, pin: Optional[str] = None) -> dict:
    """Serialise an engine Participant back to the room schema (legacy keys)."""
    return {
        "name": p.name,
        "budget": p.budget,
        "squad": [
            {
                "name": e.name,
                "role": e.role,
                "team": e.team,
                "buy_price": e.price_paid,
                "acquired_via": e.acquired_via,
            }
            for e in p.squad
        ],
        "user": user,
        "pin": pin,
    }


# --------------------------------------------------------------------------- #
# Engine <-> room mapping
# --------------------------------------------------------------------------- #
def engine_from_room(room: dict, data_dir: Optional[str] = None) -> AuctionEngine:
    """Reconstruct an AuctionEngine from a room document."""
    tournament = room.get("tournament_type", "T20 World Cup")
    config = default_config(tournament)
    # Per-room uploaded pool (e.g. FIFA) overrides the static tournament file.
    if room.get("player_pool"):
        from auction_engine import Player

        players = [
            Player(
                id=p.get("id") or _slug(p["name"]),
                name=p["name"],
                team=p.get("team", "Unknown"),
                role=p.get("role", "Unknown"),
                base_price=p.get("base_price", 0),
            )
            for p in room["player_pool"]
        ]
    else:
        kwargs = {"data_dir": data_dir} if data_dir else {}
        players = load_player_pool(tournament, **kwargs)

    participants = [participant_from_room(p) for p in room.get("participants", [])]
    state = AuctionState.from_dict(room.get("auction_state", {}))
    bid_log = [BidLogEntry(**e) for e in room.get("bid_log", [])]
    return AuctionEngine(
        config=config,
        players=players,
        participants=participants,
        state=state,
        bid_log=bid_log,
    )


def save_engine_to_room(engine: AuctionEngine, room: dict) -> None:
    """Write engine participants/state/bid log back into a room dict in place.

    Preserves each participant's ``user``/``pin`` fields from the existing room.
    """
    existing = {p["name"]: p for p in room.get("participants", [])}
    room["participants"] = [
        participant_to_room(
            p,
            user=existing.get(p.name, {}).get("user"),
            pin=existing.get(p.name, {}).get("pin"),
        )
        for p in engine.participants.values()
    ]
    room["auction_state"] = engine.state.to_dict()
    room["bid_log"] = [e.to_dict() for e in engine.bid_log]


# --------------------------------------------------------------------------- #
# CSV import application
# --------------------------------------------------------------------------- #
def apply_pool_import(room: dict, result: ParseResult, *, extend: bool = False) -> int:
    """Populate a room's player pool from a parsed pool CSV. Returns count added."""
    if result.kind != "pool" or not result.ok:
        raise RepositoryError("CSV did not parse as a valid player pool.")
    pool = list(room.get("player_pool", [])) if extend else []
    existing = {p["name"].lower() for p in pool}
    added = 0
    for pl in result.players:
        if pl.name.lower() in existing:
            continue
        pool.append(
            {
                "id": _slug(pl.name),
                "name": pl.name,
                "role": pl.role,
                "team": pl.team,
                "base_price": pl.base_price,
            }
        )
        existing.add(pl.name.lower())
        added += 1
    room["player_pool"] = pool
    return added


def apply_roster_import(room: dict, result: ParseResult, *, budget: int = DEFAULT_BUDGET) -> int:
    """Assign players to participants from a parsed roster CSV (auto-creates teams).

    The CSV reflects squads *after* the live (Zoom) auction. If a remaining budget
    is supplied per participant (a BUDGET row), it is used as the source of truth;
    otherwise the budget falls back to ``budget - sum(prices)``. Acquired players
    are marked so they're excluded from open bidding. Returns assignments applied.
    """
    if result.kind != "roster" or not result.ok:
        raise RepositoryError("CSV did not parse as a valid roster.")
    by_name = {p["name"]: p for p in room.get("participants", [])}
    spent: dict[str, int] = {}
    for a in result.assignments:
        part = by_name.get(a.participant)
        if part is None:
            part = {"name": a.participant, "budget": budget, "squad": [], "user": None, "pin": None}
            by_name[a.participant] = part
        if any(s["name"].lower() == a.player.lower() for s in part["squad"]):
            continue
        part["squad"].append(
            {"name": a.player, "role": a.role, "team": a.team,
             "buy_price": a.price, "acquired_via": "auction"}
        )
        spent[a.participant] = spent.get(a.participant, 0) + a.price

    # Ensure budget-only participants exist too.
    for name in result.budgets:
        if name not in by_name:
            by_name[name] = {"name": name, "budget": budget, "squad": [], "user": None, "pin": None}

    # Set remaining budget: explicit from CSV wins; else default - spent.
    for name, part in by_name.items():
        if name in result.budgets:
            part["budget"] = result.budgets[name]
        elif name in spent:
            part["budget"] = budget - spent[name]
    room["participants"] = list(by_name.values())
    return len(result.assignments)


# --------------------------------------------------------------------------- #
# Room creation / joining
# --------------------------------------------------------------------------- #
def _pool_role_team(room: dict) -> dict:
    """name.lower() -> (role, team) from the room's pool / tournament."""
    out = {}
    if room.get("player_pool"):
        for p in room["player_pool"]:
            out[p["name"].lower()] = (p.get("role", "Unknown"), p.get("team", "Unknown"))
    else:
        for p in load_player_pool(room.get("tournament_type", "T20 World Cup")):
            out[p.name.lower()] = (p.role, p.team)
    return out


def apply_reviewed_roster(room: dict, rows: list[dict], budgets: dict, *, budget_default: int = 0) -> int:
    """Commit an admin-reviewed roster. Each row's ``matched`` is the canonical pool
    name (so scoring works); role/team come from the pool, price from the CSV, and
    budgets are taken verbatim from the CSV. Returns rows applied."""
    rt = _pool_role_team(room)
    by_name = {p["name"]: p for p in room.get("participants", [])}
    for r in rows:
        part = by_name.get(r["participant"])
        if part is None:
            part = {"name": r["participant"], "budget": budget_default, "squad": [],
                    "user": None, "pin": None}
            by_name[r["participant"]] = part
        name = r["matched"]
        if any(s["name"].lower() == name.lower() for s in part["squad"]):
            continue
        role, team = rt.get(name.lower(), (r.get("role", "Unknown"), r.get("team", "Unknown")))
        part["squad"].append({"name": name, "role": role, "team": team,
                              "buy_price": int(r.get("price", 0)), "acquired_via": "auction"})
    for name in budgets:
        if name not in by_name:
            by_name[name] = {"name": name, "budget": budget_default, "squad": [],
                             "user": None, "pin": None}
    for name, part in by_name.items():
        if name in budgets:
            part["budget"] = budgets[name]
    room["participants"] = list(by_name.values())
    return len(rows)


def generate_room_code(existing: Optional[set[str]] = None) -> str:
    existing = existing or set()
    while True:
        code = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
        if code not in existing:
            return code


def _new_room(name: str, tournament_type: str, admin: str, admin_participating: bool) -> dict:
    participants = []
    if admin_participating:
        # No initial budget — budgets come from the uploaded CSV.
        participants.append(
            {"name": admin, "budget": 0, "squad": [], "user": admin, "pin": None}
        )
    return {
        "name": name,
        "tournament_type": tournament_type,
        "admin": admin,
        "admin_participating": admin_participating,
        "members": [admin],
        "participants": participants,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "big_auction_complete": False,
        "bidding_open": False,
        "trading_open": False,
        "unsold_players": [],
        "active_bids": [],
        "pending_trades": [],
        "gameweek_squads": {},
        "gameweek_scores": {},
        "auction_log": [],
        "auction_state": AuctionState().to_dict(),
        "bid_log": [],
    }


class Repository:
    """Binds the mapping helpers to a FirebaseStore."""

    def __init__(self, store: Optional[FirebaseStore] = None):
        self.store = store or FirebaseStore()

    def load(self) -> dict:
        return self.store.load()

    def load_room(self, code: str):
        """Cheap single-room read for hot polling paths (avoids the ~1 MB full doc)."""
        load_room = getattr(self.store, "load_room", None)
        if callable(load_room):
            return load_room(code)
        return self.store.load().get("rooms", {}).get((code or "").upper())

    def save(self, doc: dict) -> None:
        self.store.save(doc)

    def get_room(self, doc: dict, code: str) -> dict:
        room = doc.get("rooms", {}).get((code or "").upper())
        if room is None:
            raise RepositoryError("Invalid room code.")
        return room

    def create_room(
        self,
        doc: dict,
        admin: str,
        name: str,
        tournament_type: str,
        admin_participating: bool,
    ) -> str:
        if not name.strip():
            raise RepositoryError("Please enter a room name.")
        rooms = doc.setdefault("rooms", {})
        code = generate_room_code(set(rooms.keys()))
        rooms[code] = _new_room(name.strip(), tournament_type, admin, admin_participating)
        user = doc.setdefault("users", {}).setdefault(admin, {})
        user.setdefault("rooms_created", []).append(code)
        return code

    def add_team(self, room: dict, team_name: str, pin: str, budget: int = 0) -> None:
        """Admin creates a claimable team with a PIN (budget comes from the CSV)."""
        team_name = team_name.strip()
        if not team_name:
            raise RepositoryError("Team name is required.")
        if any(p["name"].lower() == team_name.lower() for p in room.get("participants", [])):
            raise RepositoryError(f"A team named '{team_name}' already exists.")
        if not (pin or "").strip():
            raise RepositoryError("A PIN is required for the team.")
        room.setdefault("participants", []).append(
            {"name": team_name, "budget": budget, "squad": [], "user": None, "pin": str(pin).strip()}
        )

    def claim_team(self, doc: dict, code: str, user: str, pin: str) -> dict:
        """Join a room by room code + team PIN only — the PIN identifies the team."""
        room = self.get_room(doc, code)
        pin = str(pin).strip()
        if not pin:
            raise RepositoryError("Enter your team PIN.")
        matches = [p for p in room.get("participants", []) if str(p.get("pin") or "") == pin]
        if not matches:
            raise RepositoryError("No team with that PIN in this room.")
        if len(matches) > 1:
            raise RepositoryError("That PIN matches more than one team — ask the admin to fix it.")
        part = matches[0]
        if part.get("user") and part["user"] != user:
            raise RepositoryError("That team has already been claimed by someone else.")
        part["user"] = user
        if user not in room.setdefault("members", []):
            room["members"].append(user)
        u = doc.setdefault("users", {}).setdefault(user, {})
        if code.upper() not in u.setdefault("rooms_joined", []):
            u["rooms_joined"].append(code.upper())
        return part
