"""The auction state machine.

Pure Python: no Reflex, no Streamlit, no network, no global state. The engine owns
the players pool, the participants (with budgets + squads), the live auction-floor
state, and an append-only bid log. Every mutating method first snapshots the full
state so :meth:`undo` can revert the last action.

Time is injected (``now`` epoch seconds) so behaviour is deterministic in tests.

Ported from the legacy live-auction fragment in ``streamlit_app.py`` (lines
663-1226); see ``PLAN.md`` §2 for the rule-by-rule mapping.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Optional

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
    STATUS_IDLE,
    STATUS_PAUSED,
    STATUS_RUNNING,
    AuctionState,
    BidLogEntry,
    EngineConfig,
    Participant,
    Player,
    RosterEntry,
)
from .rules import increment_error_message, increment_is_legal, min_next_bid


@dataclass
class ResolveResult:
    """Outcome of :meth:`AuctionEngine.resolve` / force actions."""

    kind: str                      # "sold" | "unsold" | "none"
    player_id: Optional[str] = None
    player_name: Optional[str] = None
    participant_id: Optional[str] = None
    amount: int = 0
    auction_finished: bool = False  # True when the team queue is now empty


class AuctionEngine:
    def __init__(
        self,
        config: Optional[EngineConfig] = None,
        players: Optional[list[Player]] = None,
        participants: Optional[list[Participant]] = None,
        state: Optional[AuctionState] = None,
        bid_log: Optional[list[BidLogEntry]] = None,
    ):
        self.config = config or EngineConfig()
        self.players: dict[str, Player] = {p.id: p for p in (players or [])}
        self.participants: dict[str, Participant] = {p.id: p for p in (participants or [])}
        self.state: AuctionState = state or AuctionState()
        self.bid_log: list[BidLogEntry] = list(bid_log or [])
        self._history: list[dict] = []

    # ------------------------------------------------------------------ #
    # Snapshot / undo
    # ------------------------------------------------------------------ #
    def _snapshot(self) -> None:
        """Record the current state so the next mutation can be undone."""
        self._history.append(
            {
                "participants": {pid: p.to_dict() for pid, p in self.participants.items()},
                "state": self.state.to_dict(),
                "bid_log": [e.to_dict() for e in self.bid_log],
            }
        )

    def undo(self) -> None:
        """Revert the most recent mutating action. Raises if none exists."""
        if not self._history:
            raise NothingToUndoError("There is no action to undo.")
        snap = self._history.pop()
        self.participants = {
            pid: Participant.from_dict(pd) for pid, pd in snap["participants"].items()
        }
        self.state = AuctionState.from_dict(snap["state"])
        self.bid_log = [BidLogEntry(**e) for e in snap["bid_log"]]

    @property
    def can_undo(self) -> bool:
        return bool(self._history)

    # ------------------------------------------------------------------ #
    # Lookups / helpers
    # ------------------------------------------------------------------ #
    def _require_participant(self, participant_id: str) -> Participant:
        p = self.participants.get(participant_id)
        if p is None:
            raise UnknownParticipantError(f"Unknown participant: {participant_id!r}")
        return p

    def _drafted_player_ids(self) -> set[str]:
        drafted: set[str] = set()
        for p in self.participants.values():
            for e in p.squad:
                drafted.add(e.player_id)
        return drafted

    def _category_of(self, role: str) -> Optional[str]:
        """Map a free-text role to a composition category, or None if unknown."""
        if not self.config.role_categories:
            return None
        return self.config.role_categories.get(role)

    def _would_breach_composition(self, participant: Participant, player: Player) -> bool:
        """True if adding ``player`` would exceed the max for its category."""
        comp = self.config.composition
        if not comp:
            return False
        cat = self._category_of(player.role)
        if cat is None or cat not in comp:
            return False
        _, max_allowed = comp[cat]
        current = sum(
            1
            for e in participant.squad
            if self._category_of(e.role) == cat
        )
        return current + 1 > max_allowed

    # ------------------------------------------------------------------ #
    # Auction lifecycle
    # ------------------------------------------------------------------ #
    def start_team_auction(
        self,
        team: str,
        now: float,
        order: Optional[list[str]] = None,
    ) -> None:
        """Begin auctioning the undrafted players of ``team``.

        ``order`` optionally fixes the queue (list of player ids). Otherwise all
        undrafted players from ``team`` are queued in pool order.
        """
        self._snapshot()
        drafted = self._drafted_player_ids()
        if order is not None:
            queue = [pid for pid in order if pid in self.players and pid not in drafted]
        else:
            queue = [
                pid
                for pid, pl in self.players.items()
                if pl.team == team and pid not in drafted
            ]
        if not queue:
            # Nothing to auction; revert the snapshot we just took.
            self._history.pop()
            raise InvalidStateError(f"No undrafted players available for team {team!r}.")

        self.state = AuctionState(
            status=STATUS_RUNNING,
            current_team=team,
            queue=queue,
            current_player_id=queue[0],
            current_bid=0,
            current_bidder_id=None,
            timer_ends_at=now + self.config.timer_seconds,
            opted_out=[],
            unsold=list(self.state.unsold),  # preserve unsold across teams
        )

    def nominate_player(self, player_id: str, now: float) -> None:
        """Put a single specific player on the block (manual nomination).

        Improvement over legacy team-only flow. The player must exist and be
        undrafted. Starts/continues a running auction with a one-player queue
        appended if not already queued.
        """
        if player_id not in self.players:
            raise InvalidStateError(f"Unknown player: {player_id!r}")
        if player_id in self._drafted_player_ids():
            raise InvalidStateError("That player has already been drafted.")
        self._snapshot()
        player = self.players[player_id]
        self.state.status = STATUS_RUNNING
        self.state.current_team = player.team
        self.state.queue = [player_id] + [q for q in self.state.queue if q != player_id]
        self.state.current_player_id = player_id
        self.state.current_bid = 0
        self.state.current_bidder_id = None
        self.state.opted_out = []
        self.state.timer_ends_at = now + self.config.timer_seconds

    # ------------------------------------------------------------------ #
    # Bidding
    # ------------------------------------------------------------------ #
    def place_bid(self, participant_id: str, amount: int, now: float) -> None:
        """Validate and apply a bid. Raises a subclass of AuctionError on reject."""
        if self.state.status != STATUS_RUNNING or not self.state.current_player_id:
            raise InvalidStateError("No player is currently up for auction.")

        participant = self._require_participant(participant_id)

        if participant_id in self.state.opted_out:
            raise BidError("You have opted out of bidding on this player.")
        if participant_id == self.state.current_bidder_id:
            raise BidError("You already hold the top bid.")
        if participant.squad_size >= self.config.max_squad:
            raise SquadFullError(
                f"Squad is full ({self.config.max_squad} players); cannot bid."
            )

        player = self.players[self.state.current_player_id]
        if self._would_breach_composition(participant, player):
            cat = self._category_of(player.role)
            raise CompositionError(
                f"Winning this player would exceed your limit for {cat}."
            )

        floor = self.config.starting_min_bid
        minimum = min_next_bid(self.state.current_bid, floor=floor)
        if amount < minimum:
            raise BidError(f"Bid must be at least {minimum}M.")
        if not increment_is_legal(amount):
            raise BidError(increment_error_message(amount) or "Illegal bid increment.")
        if amount > participant.budget:
            raise BudgetError(
                f"Bid {amount}M exceeds your remaining budget of {participant.budget}M."
            )

        self._snapshot()
        self.state.current_bid = amount
        self.state.current_bidder_id = participant_id
        self.state.timer_ends_at = now + self.config.timer_seconds
        self.bid_log.append(
            BidLogEntry(
                player_id=player.id,
                player_name=player.name,
                participant_id=participant_id,
                amount=amount,
                timestamp=now,
                kind="bid",
            )
        )

    def opt_out(self, participant_id: str) -> None:
        self._require_participant(participant_id)
        if self.state.status != STATUS_RUNNING:
            raise InvalidStateError("No auction is running.")
        if participant_id == self.state.current_bidder_id:
            raise BidError("You cannot opt out while holding the top bid.")
        if participant_id not in self.state.opted_out:
            self._snapshot()
            self.state.opted_out.append(participant_id)

    def revive(self, participant_id: str) -> None:
        """Admin: bring an opted-out participant back into the current bidding."""
        if participant_id in self.state.opted_out:
            self._snapshot()
            self.state.opted_out.remove(participant_id)

    # ------------------------------------------------------------------ #
    # Timer resolution & sale/pass
    # ------------------------------------------------------------------ #
    def time_remaining(self, now: float) -> float:
        if self.state.timer_ends_at is None:
            return float(self.config.timer_seconds)
        return max(0.0, self.state.timer_ends_at - now)

    def _others_active(self) -> int:
        """Active bidders excluding the current top bidder (legacy semantics)."""
        active = [
            pid for pid in self.participants if pid not in self.state.opted_out
        ]
        held = self.state.current_bidder_id
        return len(active) - (1 if held and held not in self.state.opted_out else 0)

    def pending_resolution(self, now: float) -> Optional[str]:
        """Return "sold"/"unsold" if the current player should resolve now, else None.

        Pure check — does not mutate. Mirrors legacy should_autosell / should_autopass.
        """
        if self.state.status != STATUS_RUNNING or not self.state.current_player_id:
            return None
        expired = self.time_remaining(now) <= 0
        bidder = self.state.current_bidder_id
        active_count = len(
            [pid for pid in self.participants if pid not in self.state.opted_out]
        )
        if (expired and bidder) or (bidder and self._others_active() == 0):
            return "sold"
        if (expired and not bidder) or (not bidder and active_count == 0):
            return "unsold"
        return None

    def resolve(self, now: float) -> ResolveResult:
        """Apply auto-sell/auto-pass if due; otherwise a no-op result."""
        outcome = self.pending_resolution(now)
        if outcome == "sold":
            return self.sell_current(now)
        if outcome == "unsold":
            return self.mark_unsold(now)
        return ResolveResult(kind="none")

    def _advance_queue(self, now: float) -> bool:
        """Drop the current player and move to the next. Returns True if finished."""
        cur = self.state.current_player_id
        if cur in self.state.queue:
            self.state.queue.remove(cur)
        if self.state.queue:
            self.state.current_player_id = self.state.queue[0]
            self.state.current_bid = 0
            self.state.current_bidder_id = None
            self.state.opted_out = []
            self.state.timer_ends_at = now + self.config.timer_seconds
            return False
        # Queue exhausted — auction for this team is complete.
        self.state.status = STATUS_IDLE
        self.state.current_player_id = None
        self.state.current_bid = 0
        self.state.current_bidder_id = None
        self.state.opted_out = []
        self.state.timer_ends_at = None
        return True

    def sell_current(self, now: float) -> ResolveResult:
        """Sell the current player to the current top bidder."""
        if self.state.status != STATUS_RUNNING or not self.state.current_player_id:
            raise InvalidStateError("No player is currently up for auction.")
        if not self.state.current_bidder_id:
            raise InvalidStateError("Cannot sell — there is no bid.")

        self._snapshot()
        player = self.players[self.state.current_player_id]
        winner = self.participants[self.state.current_bidder_id]
        price = self.state.current_bid

        winner.squad.append(
            RosterEntry(
                player_id=player.id,
                name=player.name,
                role=player.role,
                team=player.team,
                price_paid=price,
                acquired_via="auction",
            )
        )
        winner.budget -= price
        self.bid_log.append(
            BidLogEntry(
                player_id=player.id,
                player_name=player.name,
                participant_id=winner.id,
                amount=price,
                timestamp=now,
                kind="sold",
            )
        )
        result = ResolveResult(
            kind="sold",
            player_id=player.id,
            player_name=player.name,
            participant_id=winner.id,
            amount=price,
        )
        result.auction_finished = self._advance_queue(now)
        return result

    def mark_unsold(self, now: float) -> ResolveResult:
        """Pass on the current player (no sale)."""
        if self.state.status != STATUS_RUNNING or not self.state.current_player_id:
            raise InvalidStateError("No player is currently up for auction.")

        self._snapshot()
        player = self.players[self.state.current_player_id]
        if player.id not in self.state.unsold:
            self.state.unsold.append(player.id)
        self.bid_log.append(
            BidLogEntry(
                player_id=player.id,
                player_name=player.name,
                participant_id="",
                amount=0,
                timestamp=now,
                kind="unsold",
            )
        )
        result = ResolveResult(
            kind="unsold", player_id=player.id, player_name=player.name
        )
        result.auction_finished = self._advance_queue(now)
        return result

    # ------------------------------------------------------------------ #
    # Admin overrides
    # ------------------------------------------------------------------ #
    def force_sell(self, now: float) -> ResolveResult:
        if self.state.current_bid <= 0 or not self.state.current_bidder_id:
            raise InvalidStateError("Cannot force-sell with no bid on the player.")
        return self.sell_current(now)

    def force_unsold(self, now: float) -> ResolveResult:
        return self.mark_unsold(now)

    def pause(self) -> None:
        if self.state.status != STATUS_RUNNING:
            raise InvalidStateError("Auction is not running.")
        self._snapshot()
        self.state.status = STATUS_PAUSED

    def resume(self, now: float) -> None:
        """Resume a paused auction, granting a fresh timer (legacy fairness rule)."""
        if self.state.status != STATUS_PAUSED:
            raise InvalidStateError("Auction is not paused.")
        self._snapshot()
        self.state.status = STATUS_RUNNING
        self.state.timer_ends_at = now + self.config.timer_seconds

    # ------------------------------------------------------------------ #
    # Serialisation (for the Firebase repository + broadcasting)
    # ------------------------------------------------------------------ #
    def to_dict(self) -> dict:
        return {
            "config": self.config.to_dict(),
            "players": {pid: p.to_dict() for pid, p in self.players.items()},
            "participants": {pid: p.to_dict() for pid, p in self.participants.items()},
            "state": self.state.to_dict(),
            "bid_log": [e.to_dict() for e in self.bid_log],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "AuctionEngine":
        return cls(
            config=EngineConfig.from_dict(d.get("config", {})),
            players=[Player(**pd) for pd in d.get("players", {}).values()],
            participants=[Participant.from_dict(pd) for pd in d.get("participants", {}).values()],
            state=AuctionState.from_dict(d.get("state", {})),
            bid_log=[BidLogEntry(**e) for e in d.get("bid_log", [])],
        )
