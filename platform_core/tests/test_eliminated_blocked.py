"""Eliminated (knocked-out) participants must not be able to act.

Once a team is marked ``is_eliminated`` in a knockout round it may not bid,
trade, accept a trade, release, or set IR — enforced server-side in the ops
layer so a stale UI can't slip an action through.
"""

from datetime import datetime, timedelta

import pytest

from platform_core import bidding_ops as bo
from platform_core import market_ops as mo
from platform_core import season_ops as so
from season_engine.open_bidding import BidError
from season_engine.trading import TradeError


NOW = datetime(2026, 6, 3, 12, 0, 0)


def _room():
    return {
        "tournament_type": "FIFA World Cup 2026",
        "bidding_deadline": (NOW + timedelta(hours=3)).isoformat(),
        "player_pool": [
            {"name": "Mbappe", "role": "FWD", "team": "France"},
        ],
        "unsold_players": [{"name": "Free Agent", "role": "MID", "team": "Spain"}],
        "participants": [
            # OUT is the eliminated team; ALIVE is still in the league.
            {"name": "OUT", "budget": 100, "is_eliminated": True, "squad": [
                {"name": "Kane", "role": "FWD", "team": "England", "buy_price": 40}]},
            {"name": "ALIVE", "budget": 100, "squad": [
                {"name": "Rice", "role": "MID", "team": "England", "buy_price": 20}]},
        ],
    }


def test_eliminated_cannot_open_bid():
    with pytest.raises(BidError, match="eliminated"):
        bo.place(_room(), "OUT", "Mbappe", 10, NOW)


def test_active_team_can_still_bid():
    room = _room()
    bo.place(room, "ALIVE", "Mbappe", 10, NOW)   # no raise
    assert bo.active(room)[0]["high_bid"] == 10


def test_eliminated_cannot_propose_trade():
    with pytest.raises(TradeError, match="eliminated"):
        mo.propose_trade(_room(), "OUT", "ALIVE", ["Kane"], ["Rice"])


def test_cannot_trade_with_an_eliminated_team():
    with pytest.raises(TradeError, match="eliminated"):
        mo.propose_trade(_room(), "ALIVE", "OUT", ["Rice"], ["Kane"])


def test_eliminated_cannot_accept_trade():
    # Proposal was made to OUT while still active; OUT is now eliminated and accepts.
    room = _room()
    room["participants"][0]["is_eliminated"] = False
    tid = mo.propose_trade(room, "ALIVE", "OUT", ["Rice"], ["Kane"])
    room["participants"][0]["is_eliminated"] = True
    with pytest.raises(TradeError, match="eliminated"):
        mo.accept_trade(room, tid)


def test_eliminated_cannot_place_market_bid():
    with pytest.raises(TradeError, match="eliminated"):
        mo.place_market_bid(_room(), "OUT", "Free Agent", 10)


def test_eliminated_cannot_release():
    with pytest.raises(TradeError, match="eliminated"):
        mo.release(_room(), "OUT", "Kane")


def test_eliminated_cannot_half_price_release():
    with pytest.raises(so.SeasonError, match="eliminated"):
        so.half_price_release(_room(), "OUT", "Kane")


def test_eliminated_cannot_set_ir():
    with pytest.raises(so.SeasonError, match="eliminated"):
        so.set_ir(_room(), "OUT", "Kane")


# --- standing bids from a team that then gets eliminated ------------------- #
def test_standing_bid_not_awarded_to_eliminated_bidder():
    """A bid placed while active must NOT be awarded once the team is knocked out."""
    room = _room()
    room["participants"][0]["is_eliminated"] = False   # OUT is active for now
    bo.place(room, "OUT", "Mbappe", 10, NOW)
    assert bo.active(room)                              # bid is standing
    room["participants"][0]["is_eliminated"] = True     # now knocked out
    awarded = bo.resolve_deadline(room, NOW + timedelta(hours=4))
    assert awarded == []                               # nobody won Mbappe
    out = mo.participants_by_name(room)["OUT"]
    assert not any(e["name"] == "Mbappe" for e in out["squad"])
    assert out["budget"] == 100                        # budget untouched


def test_elimination_cancels_standing_bids():
    room = {
        "tournament_type": "IPL 2026",
        "gameweek_scores": {"1": {"Kohli": 80, "Rohit": 10}},
        "participants": [
            {"name": "A", "budget": 100, "squad": [{"name": "Kohli", "role": "BAT"}]},
            {"name": "B", "budget": 100, "squad": [{"name": "Rohit", "role": "BAT"}]},
        ],
        "open_bids": {"Star": {"high_bidder": "B", "high_bid": 20, "role": "BAT", "team": "X"}},
        "active_bids": [{"player": "Star", "participant": "B", "amount": 20}],
    }
    losers = so.eliminate_for_gameweek(room, "1", count=1)
    assert losers == ["B"]
    assert room["open_bids"] == {}          # B's standing open bid cancelled
    assert room["active_bids"] == []        # and their sealed market bid
