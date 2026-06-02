"""Shared fixtures for engine tests."""

import pytest

from auction_engine import AuctionEngine, EngineConfig, Participant, Player


def make_players():
    # Two India players, one Australia player.
    return [
        Player(id="p1", name="Player One", team="India", role="Batsman", base_price=2),
        Player(id="p2", name="Player Two", team="India", role="Bowler", base_price=2),
        Player(id="p3", name="Player Three", team="Australia", role="Batsman"),
    ]


def make_participants(budget=100):
    return [
        Participant(id="alice", name="Alice", budget=budget),
        Participant(id="bob", name="Bob", budget=budget),
        Participant(id="carol", name="Carol", budget=budget),
    ]


@pytest.fixture
def engine():
    return AuctionEngine(
        config=EngineConfig(timer_seconds=60, max_squad=30),
        players=make_players(),
        participants=make_participants(),
    )


@pytest.fixture
def running(engine):
    """Engine with the India auction started; p1 is on the block at t=1000."""
    engine.start_team_auction("India", now=1000.0)
    return engine
