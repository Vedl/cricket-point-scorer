"""Framework-free auction engine (ported from the legacy Streamlit app).

Public API:
    from auction_engine import AuctionEngine, EngineConfig, Player, Participant
"""

from .engine import AuctionEngine, ResolveResult
from .errors import (
    AuctionError,
    BidError,
    BudgetError,
    CompositionError,
    InvalidStateError,
    NothingToUndoError,
    SquadFullError,
    UnknownParticipantError,
)
from .models import (
    AuctionState,
    BidLogEntry,
    EngineConfig,
    Participant,
    Player,
    RosterEntry,
)
from .rules import increment_for, increment_is_legal, min_next_bid

__all__ = [
    "AuctionEngine",
    "ResolveResult",
    "AuctionState",
    "BidLogEntry",
    "EngineConfig",
    "Participant",
    "Player",
    "RosterEntry",
    "AuctionError",
    "BidError",
    "BudgetError",
    "CompositionError",
    "InvalidStateError",
    "NothingToUndoError",
    "SquadFullError",
    "UnknownParticipantError",
    "increment_for",
    "increment_is_legal",
    "min_next_bid",
]
