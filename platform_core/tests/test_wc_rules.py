"""World-Cup league rules: KO nations, IR fee/bench everywhere (football),
locked-snapshot scoring, loan protections, pure-cash re-pricing, accent search."""

import pytest

from platform_core import bidding_ops as bo
from platform_core import season_ops as so
from platform_core.textutil import fold
from season_engine.open_bidding import BidError
from season_engine.squad_lock import lock_participant
from season_engine.trading import TradeError, apply_trade, validate_trade


def _fb_room():
    return {
        "tournament_type": "FIFA World Cup 2026",
        "gw1_locked": True,
        "player_pool": [
            {"name": "Désiré Doué", "role": "Forward", "team": "France"},
            {"name": "Erling Haaland", "role": "Forward", "team": "Norway"},
            {"name": "Achraf Hakimi", "role": "Defender", "team": "Morocco"},
            {"name": "Rodri", "role": "Midfielder", "team": "Spain"},
        ],
        "participants": [
            {"name": "Alice", "budget": 50, "squad": [
                {"name": "Mbappé", "role": "Forward", "team": "France", "buy_price": 40},
                {"name": "Saka", "role": "Forward", "team": "England", "buy_price": 20},
                {"name": "Vitinha", "role": "Midfielder", "team": "Portugal",
                 "buy_price": 30, "acquired_via": "loan"},
            ]},
            {"name": "Bob", "budget": 50, "squad": [
                {"name": "Bellingham", "role": "Midfielder", "team": "England", "buy_price": 35},
            ]},
        ],
    }


# --- knocked-out nations -------------------------------------------------- #
def test_ko_release_is_half_price_and_keeps_allowance():
    room = _fb_room()
    room["knocked_out_countries"] = ["France"]
    refund = so.half_price_release(room, "Alice", "Mbappé")
    assert refund == 20                       # half of 40
    alice = room["participants"][0]
    assert alice.get("half_releases_this_gw", 0) == 0   # allowance untouched
    # The normal paid release for the gameweek is still available afterwards.
    refund2 = so.half_price_release(room, "Alice", "Saka")
    assert refund2 == 10
    assert alice["half_releases_this_gw"] == 1


def test_ko_blocks_open_bids_and_cancels_standing_ones():
    room = _fb_room()
    room["bidding_deadline"] = "2099-01-01T00:00"
    from datetime import datetime
    now = datetime(2098, 12, 1)
    bo.place(room, "Bob", "Désiré Doué", 5, now)
    assert "Désiré Doué" in room["open_bids"]
    cancelled = so.mark_country_knocked_out(room, "France", True)
    assert cancelled == ["Désiré Doué"]
    assert "Désiré Doué" not in room["open_bids"]
    with pytest.raises(BidError):
        bo.place(room, "Bob", "Désiré Doué", 5, now)
    # hidden from the available list, restored on undo
    assert all(p["team"] != "France" for p in bo.available_players(room))
    so.mark_country_knocked_out(room, "France", False)
    assert any(p["team"] == "France" for p in bo.available_players(room))


# --- accent-insensitive search + filters ---------------------------------- #
def test_fold_strips_accents():
    assert fold("Désiré Doué") == "desire doue"
    assert fold("Nicolò") == "nicolo"
    assert fold("Bałka-Øst") == "balka-ost"


def test_available_search_ignores_accents_and_combines_filters():
    room = _fb_room()
    hits = bo.available_players(room, search="desire doue")
    assert [p["name"] for p in hits] == ["Désiré Doué"]
    hits = bo.available_players(room, search="haa", country="Norway", role="Forward")
    assert [p["name"] for p in hits] == ["Erling Haaland"]
    assert bo.available_players(room, search="haa", country="Spain") == []


def test_place_bid_accepts_unaccented_name():
    room = _fb_room()
    room["bidding_deadline"] = "2099-01-01T00:00"
    from datetime import datetime
    bo.place(room, "Bob", "desire doue", 5, datetime(2098, 12, 1))
    assert "Désiré Doué" in room["open_bids"]


# --- loan protections ------------------------------------------------------ #
def test_loaned_player_cannot_be_released():
    room = _fb_room()
    with pytest.raises(so.SeasonError):
        so.half_price_release(room, "Alice", "Vitinha")


def test_loaned_player_cannot_be_traded():
    room = _fb_room()
    a, b = room["participants"]
    errors = validate_trade(a, b, ["Vitinha"], [], 0, 10)
    assert any("on loan" in e for e in errors)


def test_lock_trim_never_drops_loaned_player():
    p = {"name": "P", "budget": 100, "ir": None, "squad": (
        [{"name": "loaner", "role": "MID", "team": "X", "buy_price": 1,
          "acquired_via": "loan"}] +
        [{"name": f"p{i}", "role": "MID", "team": "X", "buy_price": 5 + i}
         for i in range(20)])}
    released, _ = lock_participant(p)
    assert all(r["name"] != "loaner" for r in released)
    assert len(p["squad"]) == 19


def test_loan_lifecycle_snapshot_then_return():
    """Loaned player appears in the borrower's locked squad for the loan GW,
    then returns to the owner (original entry intact) when the GW advances."""
    from platform_core import admin_ops as ao
    room = _fb_room()
    room["current_gameweek"] = 1
    a, b = room["participants"]
    # Alice loans Mbappé to Bob, returning at GW2.
    ao.loan_player(room, "Alice", "Bob", "Mbappé", "2")
    assert any(e["name"] == "Mbappé" for e in b["squad"])
    so.lock_gameweek(room, "1")
    snap = room["gameweek_squads"]["1"]
    assert any(s["name"] == "Mbappé" for s in snap["Bob"]["squad"])    # in borrower's lock
    assert all(s["name"] != "Mbappé" for s in snap["Alice"]["squad"])
    so.advance_gameweek(room)                                          # GW1 → GW2
    entry = next((e for e in a["squad"] if e["name"] == "Mbappé"), None)
    assert entry is not None and entry.get("buy_price") == 40          # back, price intact
    assert all(e["name"] != "Mbappé" for e in b["squad"])
    assert room.get("active_loans") == []


# --- IR rules: only bind at a FULL (>= 19) squad ----------------------------- #
def test_ir_ignored_below_19_no_fee_and_counts_in_best11():
    room = _fb_room()
    room["participants"][0]["ir"] = "Saka"
    room["participants"][1]["ir"] = "Bellingham"
    so.lock_gameweek(room, "2")
    alice = room["participants"][0]
    assert alice["budget"] == 50           # no 2M fee below 19 players
    room["gameweek_scores"] = {"2": {"Bellingham": 99, "Mbappé": 10}}
    rows = so.compute_gameweek_standings(room, "2")
    by = {r["participant"]: r["points"] for r in rows}
    assert by["Bob"] == 99                 # IR ignored below 19 — points count


def test_ir_fee_and_bench_at_19():
    room = _fb_room()
    p = room["participants"][1]
    p["squad"] = [{"name": f"p{i}", "role": "Midfielder", "team": "England",
                   "buy_price": i + 1} for i in range(19)]
    p["ir"] = "p0"
    so.lock_gameweek(room, "2")
    assert p["budget"] == 48               # 2M fee at a full squad
    room["gameweek_scores"] = {"2": {"p0": 99, "p1": 7}}
    rows = so.compute_gameweek_standings(room, "2")
    by = {r["participant"]: r["points"] for r in rows}
    assert by["Bob"] == 7                  # IR'd p0's 99 excluded at >= 19


def test_gameweek_points_use_locked_snapshot_not_live_squad():
    room = _fb_room()
    so.lock_gameweek(room, "2")
    room["gameweek_scores"] = {"2": {"Mbappé": 10, "NewGuy": 50}}
    # After the lock, Alice somehow acquires NewGuy — must NOT count for GW2.
    room["participants"][0]["squad"].append(
        {"name": "NewGuy", "role": "Forward", "team": "Spain", "buy_price": 5})
    rows = so.compute_gameweek_standings(room, "2")
    by = {r["participant"]: r["points"] for r in rows}
    assert by["Alice"] == 10


# --- random tie-breaks ------------------------------------------------------ #
def test_trim_tie_break_random_among_cheapest():
    seen = set()
    for _ in range(40):
        p = {"name": "P", "budget": 100, "ir": None, "squad": (
            [{"name": "tie_a", "role": "MID", "team": "X", "buy_price": 5},
             {"name": "tie_b", "role": "MID", "team": "X", "buy_price": 5}] +
            [{"name": f"p{i}", "role": "MID", "team": "X", "buy_price": 10 + i}
             for i in range(18)])}
        released, _ = lock_participant(p)
        assert len(released) == 1 and released[0]["name"] in ("tie_a", "tie_b")
        seen.add(released[0]["name"])
    assert seen == {"tie_a", "tie_b"}


def test_forced_ir_tie_break_random_among_most_expensive():
    seen = set()
    for _ in range(40):
        p = {"name": "P", "budget": 100, "ir": None, "squad": (
            [{"name": "big_a", "role": "MID", "team": "X", "buy_price": 50},
             {"name": "big_b", "role": "MID", "team": "X", "buy_price": 50}] +
            [{"name": f"p{i}", "role": "MID", "team": "X", "buy_price": 5}
             for i in range(17)])}
        lock_participant(p)
        assert p["ir"] in ("big_a", "big_b")
        seen.add(p["ir"])
    assert seen == {"big_a", "big_b"}


# --- pure-cash trade re-pricing --------------------------------------------- #
def test_pure_cash_trade_reprices_player():
    a = {"name": "A", "budget": 50,
         "squad": [{"name": "X", "role": "FWD", "team": "France", "buy_price": 10}]}
    b = {"name": "B", "budget": 50, "squad": []}
    apply_trade(a, b, ["X"], [], 0, 25)     # B buys X for 25M cash
    assert b["squad"][0]["buy_price"] == 25
    assert a["budget"] == 75 and b["budget"] == 25


def test_player_swap_keeps_original_buy_prices():
    a = {"name": "A", "budget": 50,
         "squad": [{"name": "X", "role": "FWD", "team": "France", "buy_price": 10}]}
    b = {"name": "B", "budget": 50,
         "squad": [{"name": "Y", "role": "MID", "team": "Spain", "buy_price": 7}]}
    apply_trade(a, b, ["X"], ["Y"], 5, 0)   # swap + cash → NOT a pure buy
    assert next(e for e in b["squad"] if e["name"] == "X")["buy_price"] == 10
    assert next(e for e in a["squad"] if e["name"] == "Y")["buy_price"] == 7


def test_multi_player_trade_allowed_but_not_for_pure_cash():
    a = {"name": "A", "budget": 50, "squad": [
        {"name": "X1", "role": "FWD", "team": "Spain", "buy_price": 10},
        {"name": "X2", "role": "MID", "team": "Spain", "buy_price": 8}]}
    b = {"name": "B", "budget": 50, "squad": [
        {"name": "Y1", "role": "DEF", "team": "England", "buy_price": 6}]}
    # 2-for-1 swap with cash: fine, original prices kept.
    assert validate_trade(a, b, ["X1", "X2"], ["Y1"], 0, 5) == []
    # 2 players for cash only: rejected with the owner's message.
    errors = validate_trade(a, b, ["X1", "X2"], [], 0, 20)
    assert any("Only 1 player is allowed in a pure cash deal" in e for e in errors)
    # 1 player for cash only stays allowed.
    assert validate_trade(a, b, ["X1"], [], 0, 20) == []


def test_ko_nation_players_cannot_be_traded():
    room = _fb_room()
    room["knocked_out_countries"] = ["France"]
    from platform_core import market_ops as mo
    with pytest.raises(TradeError, match="knocked out"):
        mo.propose_trade(room, "Alice", "Bob", ["Mbappé"], [], 0, 10)
    # Non-KO players still tradable.
    mo.propose_trade(room, "Alice", "Bob", ["Saka"], [], 0, 10)


def test_unresolved_trades_auto_rejected_at_lock():
    room = _fb_room()
    from platform_core import market_ops as mo
    t1 = mo.propose_trade(room, "Alice", "Bob", ["Saka"], [], 0, 10)
    t2 = mo.propose_trade(room, "Alice", "Bob", ["Mbappé"], ["Bellingham"], 0, 0)
    mo.accept_trade(room, t2)              # awaiting_admin
    so.lock_gameweek(room, "1")
    statuses = {t["id"]: t["status"] for t in room["pending_trades"]}
    assert statuses[t1] == "auto_rejected"
    assert statuses[t2] == "auto_rejected"
    assert mo.trades_awaiting_admin(room) == []


# --- deadline automation helper --------------------------------------------- #
def test_deadline_work_due():
    from datetime import datetime, timedelta
    room = _fb_room()
    now = datetime(2026, 6, 11, 22, 0)
    assert so.deadline_work_due(room, now) is False          # no deadline set
    room["bidding_deadline"] = "2026-06-11T22:30"
    assert so.deadline_work_due(room, now) is False          # not reached yet
    assert so.deadline_work_due(room, now + timedelta(minutes=31)) is True   # award due
    room["bids_resolved"] = True
    assert so.deadline_work_due(room, now + timedelta(minutes=45)) is False  # mid-window
    assert so.deadline_work_due(room, now + timedelta(minutes=61)) is True   # lock due
    room["locked_for_deadline"] = True
    assert so.deadline_work_due(room, now + timedelta(minutes=61)) is False
