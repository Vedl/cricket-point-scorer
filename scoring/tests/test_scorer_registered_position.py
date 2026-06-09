"""End-to-end test of the registered-position rule through the real scorer.

We stub WhoScored (the network) and the numeric scoring formulas, then assert that
``calc_all_players_whoscored`` emits the REGISTERED-position score for every eligible
slot — proving the Kimmich rule holds through the actual production code path, not
just the isolated helper.
"""

import sys
import types

import pandas as pd
import pytest

import football_score_calculator as fsc


def _player_row(name, played_pos, **extra):
    row = {
        "Unnamed: 0_level_0_Player": name,
        "Pos": played_pos,
        "Team": "Home",
        "minutes_played": 90,
        "goals_scored": 0,
        "goals_conceded": 0,
    }
    row.update(extra)
    return row


def _install_fakes(monkeypatch, df, per_pos_scores):
    # Stub the network adapter (the inner `import whoscored_adapter`).
    fake_adapter = types.ModuleType("whoscored_adapter")
    fake_adapter.get_whoscored_stats = lambda url: df
    monkeypatch.setitem(sys.modules, "whoscored_adapter", fake_adapter)
    # Stub the numeric formulas so each position has a distinct, known score.
    monkeypatch.setattr(fsc, "score_calc_wrapper",
                        lambda pos, d, ts, tc: per_pos_scores[pos])


def _by_pos(out, name):
    rows = out[out["Player"] == name]
    return dict(zip(rows["Position"], rows["Score"]))


def test_registered_def_played_mid_scores_as_def_in_both_slots(monkeypatch):
    df = pd.DataFrame([_player_row("Kimmich", "MID")])
    _install_fakes(monkeypatch, df, {"DEF": 40, "MID": 55, "FWD": 70, "GK": 10})
    out = fsc.calc_all_players_whoscored("http://x", registered_positions={"Kimmich": "Defender"})
    # DEFENDER score (40) appears under BOTH his registered DEF slot and his played
    # MID slot — never the higher MID score (55).
    assert _by_pos(out, "Kimmich") == {"DEF": 40, "MID": 40}


def test_registered_equals_played_is_single_slot(monkeypatch):
    df = pd.DataFrame([_player_row("Musiala", "MID")])
    _install_fakes(monkeypatch, df, {"DEF": 40, "MID": 55, "FWD": 70, "GK": 10})
    out = fsc.calc_all_players_whoscored("http://x", registered_positions={"Musiala": "Midfielder"})
    assert _by_pos(out, "Musiala") == {"MID": 55}


def test_player_absent_from_database_uses_played_position(monkeypatch):
    df = pd.DataFrame([_player_row("Trialist", "FWD")])
    _install_fakes(monkeypatch, df, {"DEF": 40, "MID": 55, "FWD": 70, "GK": 10})
    out = fsc.calc_all_players_whoscored("http://x", registered_positions={})
    assert _by_pos(out, "Trialist") == {"FWD": 70}


def test_zero_minute_player_is_dropped(monkeypatch):
    df = pd.DataFrame([_player_row("BenchWarmer", "FWD", minutes_played=0)])
    _install_fakes(monkeypatch, df, {"DEF": 40, "MID": 55, "FWD": 70, "GK": 10})
    out = fsc.calc_all_players_whoscored("http://x", registered_positions={"BenchWarmer": "Forward"})
    assert out[out["Player"] == "BenchWarmer"]["Score"].dropna().empty
