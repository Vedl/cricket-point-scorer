"""Pure data structures for the auction engine.

These are plain dataclasses with no I/O and no framework imports. Everything is
JSON-serialisable via :func:`dataclasses.asdict` so the repository layer can persist
a snapshot to Firebase and the Reflex layer can broadcast it.

Money is represented as integers (millions, "M") to mirror the legacy app, which
only ever dealt in whole-million bids.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional


# --- Squad-composition role categories -------------------------------------
# Mirrors the legacy Best-11 classifier. Composition limits are optional and
# configured per event; cricket events ship with them disabled (see EngineConfig).
CRICKET_ROLES = ("WK", "BAT", "AR", "BWL")
FOOTBALL_ROLES = ("GK", "DEF", "MID", "FWD")


@dataclass
class Player:
    """A player available to be auctioned."""

    id: str
    name: str
    team: str = "Unknown"          # real-world team / country
    role: str = "Unknown"          # free-text role as it appears in the player pool
    base_price: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RosterEntry:
    """A player a participant has won/acquired."""

    player_id: str
    name: str
    role: str
    team: str
    price_paid: int
    acquired_via: str = "auction"  # auction | market | trade | loan | admin

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Participant:
    """A team manager taking part in the auction."""

    id: str
    name: str
    budget: int
    squad: list[RosterEntry] = field(default_factory=list)

    @property
    def squad_size(self) -> int:
        return len(self.squad)

    def has_player(self, player_id: str) -> bool:
        return any(e.player_id == player_id for e in self.squad)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "budget": self.budget,
            "squad": [e.to_dict() for e in self.squad],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Participant":
        return cls(
            id=d["id"],
            name=d["name"],
            budget=d["budget"],
            squad=[RosterEntry(**e) for e in d.get("squad", [])],
        )


@dataclass
class BidLogEntry:
    """One append-only entry in the auction bid log."""

    player_id: str
    player_name: str
    participant_id: str
    amount: int
    timestamp: float          # epoch seconds (engine clock)
    kind: str = "bid"         # bid | sold | unsold

    def to_dict(self) -> dict:
        return asdict(self)


# --- Auction status ---------------------------------------------------------
STATUS_IDLE = "idle"          # no auction set up / between teams
STATUS_RUNNING = "running"    # a player is on the block, bidding open
STATUS_PAUSED = "paused"      # admin paused; state frozen


@dataclass
class AuctionState:
    """The live state of one running auction within a room.

    Holds only the *auction floor* state. Participants, rosters and the bid log
    live on the engine alongside it.
    """

    status: str = STATUS_IDLE
    current_team: Optional[str] = None
    queue: list[str] = field(default_factory=list)   # remaining player ids (incl. current)
    current_player_id: Optional[str] = None
    current_bid: int = 0
    current_bidder_id: Optional[str] = None
    timer_ends_at: Optional[float] = None             # epoch seconds; None until first activity
    opted_out: list[str] = field(default_factory=list)
    unsold: list[str] = field(default_factory=list)   # player ids passed in this auction

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "AuctionState":
        return cls(
            status=d.get("status", STATUS_IDLE),
            current_team=d.get("current_team"),
            queue=list(d.get("queue", [])),
            current_player_id=d.get("current_player_id"),
            current_bid=d.get("current_bid", 0),
            current_bidder_id=d.get("current_bidder_id"),
            timer_ends_at=d.get("timer_ends_at"),
            opted_out=list(d.get("opted_out", [])),
            unsold=list(d.get("unsold", [])),
        )


@dataclass
class EngineConfig:
    """Per-event auction rules. Defaults mirror the legacy cricket auction."""

    timer_seconds: int = 60
    starting_min_bid: int = 5            # legacy: min_bid = max(5, current+increment)
    max_squad: int = 30
    # Composition limits: {role: (min, max)}. Empty dict => no composition enforcement
    # (legacy cricket behaviour — role limits only ever applied at Best-11 scoring).
    composition: dict[str, tuple[int, int]] = field(default_factory=dict)
    # Maps a free-text player role to a composition category. Only consulted when
    # composition is non-empty.
    role_categories: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "timer_seconds": self.timer_seconds,
            "starting_min_bid": self.starting_min_bid,
            "max_squad": self.max_squad,
            "composition": {k: list(v) for k, v in self.composition.items()},
            "role_categories": dict(self.role_categories),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "EngineConfig":
        return cls(
            timer_seconds=d.get("timer_seconds", 60),
            starting_min_bid=d.get("starting_min_bid", 5),
            max_squad=d.get("max_squad", 30),
            composition={k: tuple(v) for k, v in d.get("composition", {}).items()},
            role_categories=dict(d.get("role_categories", {})),
        )
