"""Exceptions raised by the auction engine.

All are subclasses of ``AuctionError`` so callers (Reflex state classes) can catch
the base type and surface ``str(exc)`` to the user as a clean validation message.
"""


class AuctionError(Exception):
    """Base class for all auction rule violations."""


class InvalidStateError(AuctionError):
    """An action was attempted that the current auction status does not allow."""


class UnknownParticipantError(AuctionError):
    """Referenced a participant id that does not exist in this auction."""


class BidError(AuctionError):
    """A bid was rejected (too low, wrong increment, bidder ineligible, ...)."""


class BudgetError(BidError):
    """The bid exceeds the participant's remaining budget."""


class SquadFullError(BidError):
    """Winning this player would exceed the participant's squad-size cap."""


class CompositionError(BidError):
    """Winning this player would breach the event's squad-composition limits."""


class NothingToUndoError(AuctionError):
    """Undo was requested but no prior action exists to revert."""
