"""Tests for the auction state machine."""

import pytest

from auction_engine import (
    AuctionEngine,
    BidError,
    BudgetError,
    CompositionError,
    EngineConfig,
    InvalidStateError,
    NothingToUndoError,
    Participant,
    Player,
    SquadFullError,
)
from auction_engine.models import STATUS_IDLE, STATUS_PAUSED, STATUS_RUNNING


# --------------------------------------------------------------------------- #
# start_team_auction
# --------------------------------------------------------------------------- #
def test_start_builds_queue_from_team(running):
    assert running.state.status == STATUS_RUNNING
    assert running.state.current_team == "India"
    assert running.state.queue == ["p1", "p2"]      # only India players
    assert running.state.current_player_id == "p1"
    assert running.state.timer_ends_at == 1000.0 + 60


def test_start_excludes_already_drafted(engine):
    from auction_engine import RosterEntry

    # Alice already owns p1, so it should not be queued.
    engine.participants["alice"].squad.append(
        RosterEntry("p1", "Player One", "Batsman", "India", 10)
    )
    engine.start_team_auction("India", now=0.0)
    assert engine.state.queue == ["p2"]


def test_start_with_explicit_order(engine):
    engine.start_team_auction("India", now=0.0, order=["p2", "p1"])
    assert engine.state.queue == ["p2", "p1"]
    assert engine.state.current_player_id == "p2"


def test_start_no_players_raises_and_leaves_no_history(engine):
    with pytest.raises(InvalidStateError):
        engine.start_team_auction("Nonexistent", now=0.0)
    assert engine.can_undo is False


# --------------------------------------------------------------------------- #
# place_bid validation
# --------------------------------------------------------------------------- #
def test_first_bid_minimum_is_floor(running):
    with pytest.raises(BidError, match="at least 5M"):
        running.place_bid("alice", 4, now=1001.0)
    running.place_bid("alice", 5, now=1001.0)
    assert running.state.current_bid == 5
    assert running.state.current_bidder_id == "alice"


def test_bid_resets_timer(running):
    running.place_bid("alice", 5, now=1030.0)
    assert running.state.timer_ends_at == 1030.0 + 60


def test_bid_must_beat_min_next(running):
    running.place_bid("alice", 10, now=1001.0)
    # current 10 -> min next 11
    with pytest.raises(BidError, match="at least 11M"):
        running.place_bid("bob", 10, now=1002.0)
    running.place_bid("bob", 11, now=1002.0)
    assert running.state.current_bidder_id == "bob"


def test_illegal_increment_rejected(running):
    running.place_bid("alice", 50, now=1001.0)        # legal; min next is now 55
    # 57 clears the 55 minimum but is not a multiple of 5 -> increment rule fires.
    with pytest.raises(BidError, match="increments of 5"):
        running.place_bid("bob", 57, now=1002.0)


def test_over_budget_rejected(engine):
    engine.participants["alice"].budget = 8
    engine.start_team_auction("India", now=0.0)
    with pytest.raises(BudgetError, match="exceeds your remaining budget"):
        engine.place_bid("alice", 9, now=1.0)


def test_cannot_bid_when_opted_out(running):
    running.opt_out("alice")
    with pytest.raises(BidError, match="opted out"):
        running.place_bid("alice", 5, now=1001.0)


def test_cannot_bid_against_self(running):
    running.place_bid("alice", 5, now=1001.0)
    with pytest.raises(BidError, match="already hold"):
        running.place_bid("alice", 6, now=1002.0)


def test_unknown_participant_rejected(running):
    from auction_engine import UnknownParticipantError

    with pytest.raises(UnknownParticipantError):
        running.place_bid("nobody", 5, now=1001.0)


def test_bid_requires_running(engine):
    with pytest.raises(InvalidStateError):
        engine.place_bid("alice", 5, now=1.0)


# --------------------------------------------------------------------------- #
# Squad cap + composition (spec hard-requirement: enforced server-side)
# --------------------------------------------------------------------------- #
def test_squad_full_blocks_bid():
    from auction_engine import RosterEntry

    cfg = EngineConfig(max_squad=1)
    p = Participant(id="alice", name="Alice", budget=100)
    p.squad.append(RosterEntry("x", "X", "Batsman", "India", 1))
    eng = AuctionEngine(
        config=cfg,
        players=[Player("p1", "P1", "India", "Batsman")],
        participants=[p],
    )
    eng.start_team_auction("India", now=0.0)
    with pytest.raises(SquadFullError):
        eng.place_bid("alice", 5, now=1.0)


def test_composition_limit_blocks_bid():
    from auction_engine import RosterEntry

    cfg = EngineConfig(
        max_squad=30,
        composition={"BWL": (0, 1)},                     # at most 1 bowler
        role_categories={"Bowler": "BWL", "Batsman": "BAT"},
    )
    p = Participant(id="alice", name="Alice", budget=100)
    p.squad.append(RosterEntry("b0", "Bowler0", "Bowler", "India", 1))  # already 1 BWL
    eng = AuctionEngine(
        config=cfg,
        players=[Player("p1", "P1", "India", "Bowler")],
        participants=[p],
    )
    eng.start_team_auction("India", now=0.0)
    with pytest.raises(CompositionError):
        eng.place_bid("alice", 5, now=1.0)


def test_composition_disabled_by_default(running):
    # Default cricket config has empty composition -> never blocks.
    for amt, who, t in [(5, "alice", 1001.0), (6, "bob", 1002.0)]:
        running.place_bid(who, amt, now=t)
    assert running.state.current_bidder_id == "bob"


# --------------------------------------------------------------------------- #
# opt-out / revive
# --------------------------------------------------------------------------- #
def test_opt_out_and_revive(running):
    running.opt_out("bob")
    assert "bob" in running.state.opted_out
    running.revive("bob")
    assert "bob" not in running.state.opted_out


def test_cannot_opt_out_while_holding(running):
    running.place_bid("alice", 5, now=1001.0)
    with pytest.raises(BidError):
        running.opt_out("alice")


# --------------------------------------------------------------------------- #
# Timer resolution: sell / unsold
# --------------------------------------------------------------------------- #
def test_autosell_on_timer_expiry(running):
    running.place_bid("alice", 20, now=1001.0)
    assert running.pending_resolution(now=1001.0 + 30) is None   # still time
    assert running.pending_resolution(now=1001.0 + 61) == "sold"
    result = running.resolve(now=1001.0 + 61)
    assert result.kind == "sold"
    assert result.participant_id == "alice"
    assert result.amount == 20


def test_autosell_when_all_others_opt_out(running):
    running.place_bid("alice", 20, now=1001.0)
    running.opt_out("bob")
    running.opt_out("carol")
    # Even though timer not expired, no other active bidder -> sold.
    assert running.pending_resolution(now=1002.0) == "sold"


def test_autopass_on_timer_with_no_bid(running):
    assert running.pending_resolution(now=1000.0 + 61) == "unsold"
    result = running.resolve(now=1000.0 + 61)
    assert result.kind == "unsold"
    assert result.player_id == "p1"


def test_autopass_when_everyone_opts_out_no_bid(running):
    running.opt_out("alice")
    running.opt_out("bob")
    running.opt_out("carol")
    assert running.pending_resolution(now=1001.0) == "unsold"


# --------------------------------------------------------------------------- #
# Sale effects + queue advance
# --------------------------------------------------------------------------- #
def test_sale_updates_budget_squad_log_and_advances(running):
    running.place_bid("alice", 30, now=1001.0)
    running.resolve(now=1001.0 + 61)
    alice = running.participants["alice"]
    assert alice.budget == 70
    assert alice.squad_size == 1
    assert alice.squad[0].player_id == "p1"
    assert alice.squad[0].price_paid == 30
    # bid log has the bid + the sold entry
    kinds = [e.kind for e in running.bid_log]
    assert kinds == ["bid", "sold"]
    # advanced to next player
    assert running.state.current_player_id == "p2"
    assert running.state.current_bid == 0
    assert running.state.current_bidder_id is None


def test_auction_finishes_when_queue_empty(running):
    # Sell p1, then pass p2 -> queue empty -> idle.
    running.place_bid("alice", 10, now=1001.0)
    running.resolve(now=1001.0 + 61)
    r2 = running.resolve(now=1001.0 + 61 + 61)   # p2 unsold on expiry
    assert r2.kind == "unsold"
    assert r2.auction_finished is True
    assert running.state.status == STATUS_IDLE
    assert running.state.current_player_id is None
    assert "p2" in running.state.unsold


# --------------------------------------------------------------------------- #
# Admin overrides
# --------------------------------------------------------------------------- #
def test_force_sell_requires_a_bid(running):
    with pytest.raises(InvalidStateError):
        running.force_sell(now=1001.0)
    running.place_bid("alice", 7, now=1001.0)
    result = running.force_sell(now=1002.0)
    assert result.kind == "sold"
    assert running.participants["alice"].budget == 93


def test_force_unsold(running):
    result = running.force_unsold(now=1001.0)
    assert result.kind == "unsold"
    assert running.state.current_player_id == "p2"


def test_pause_and_resume(running):
    running.pause()
    assert running.state.status == STATUS_PAUSED
    # No resolution while paused.
    assert running.pending_resolution(now=1000.0 + 999) is None
    running.resume(now=2000.0)
    assert running.state.status == STATUS_RUNNING
    assert running.state.timer_ends_at == 2000.0 + 60


# --------------------------------------------------------------------------- #
# Manual nomination (improvement over legacy)
# --------------------------------------------------------------------------- #
def test_nominate_player(engine):
    engine.nominate_player("p3", now=500.0)
    assert engine.state.status == STATUS_RUNNING
    assert engine.state.current_player_id == "p3"
    assert engine.state.timer_ends_at == 500.0 + 60


def test_nominate_drafted_player_rejected(running):
    running.place_bid("alice", 5, now=1001.0)
    running.resolve(now=1001.0 + 61)            # p1 sold to alice
    with pytest.raises(InvalidStateError):
        running.nominate_player("p1", now=2000.0)


# --------------------------------------------------------------------------- #
# Undo
# --------------------------------------------------------------------------- #
def test_undo_reverts_bid(running):
    running.place_bid("alice", 25, now=1001.0)
    assert running.state.current_bid == 25
    running.undo()
    assert running.state.current_bid == 0
    assert running.state.current_bidder_id is None
    assert running.bid_log == []


def test_undo_reverts_sale(running):
    running.place_bid("alice", 25, now=1001.0)
    running.resolve(now=1001.0 + 61)
    assert running.participants["alice"].budget == 75
    running.undo()                              # undo the sale
    assert running.participants["alice"].budget == 100
    assert running.participants["alice"].squad_size == 0
    assert running.state.current_player_id == "p1"
    assert running.state.current_bidder_id == "alice"   # back to pre-sale state


def test_undo_multiple_steps(running):
    running.place_bid("alice", 10, now=1001.0)
    running.place_bid("bob", 11, now=1002.0)
    running.undo()
    assert running.state.current_bidder_id == "alice"
    running.undo()
    assert running.state.current_bidder_id is None


def test_undo_nothing_raises(engine):
    with pytest.raises(NothingToUndoError):
        engine.undo()


# --------------------------------------------------------------------------- #
# Serialisation round-trip
# --------------------------------------------------------------------------- #
def test_serialisation_round_trip(running):
    running.place_bid("alice", 15, now=1001.0)
    d = running.to_dict()
    clone = AuctionEngine.from_dict(d)
    assert clone.state.current_bid == 15
    assert clone.state.current_bidder_id == "alice"
    assert clone.state.queue == ["p1", "p2"]
    assert clone.participants["alice"].budget == 100
    assert clone.to_dict() == d
