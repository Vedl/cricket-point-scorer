"""Exhaustive tests for the positional eligibility + scoring rule.

This is the rule that decides who is eligible for which Best-11 slot and — crucially
— that a player's points are ALWAYS computed from their REGISTERED position, never
the position they happened to play. Getting this wrong could change who wins, so it
is tested in depth.
"""

import pytest

from scoring.positions import (
    eligible_positions,
    map_role_to_pos,
    position_score_map,
)


# --------------------------------------------------------------------------- #
# map_role_to_pos
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("role,expected", [
    ("GK", "GK"), ("Goalkeeper", "GK"), ("gk", "GK"),
    ("DEF", "DEF"), ("Defender", "DEF"), ("Centre Back", "DEF"),
    ("CB", "DEF"), ("Right Back", "DEF"), ("RB", "DEF"), ("LWB", "DEF"),
    ("MID", "MID"), ("Midfielder", "MID"), ("Central Midfield", "MID"),
    ("CDM", "MID"), ("CAM", "MID"), ("DM", "MID"), ("AM", "MID"), ("MC", "MID"),
    ("FWD", "FWD"), ("Forward", "FWD"), ("Striker", "FWD"), ("Winger", "FWD"),
    ("LW", "FWD"), ("CF", "FWD"), ("ST", "FWD"),
])
def test_map_role_to_pos_recognised(role, expected):
    assert map_role_to_pos(role) == expected


@pytest.mark.parametrize("role", ["", None, "Manager", "Coach", "xyz", "   "])
def test_map_role_to_pos_unknown_returns_none(role):
    assert map_role_to_pos(role) is None


def test_map_role_to_pos_is_case_insensitive():
    assert map_role_to_pos("cEnTrE bAcK") == "DEF"
    assert map_role_to_pos("  striker ") == "FWD"


# --------------------------------------------------------------------------- #
# eligible_positions
# --------------------------------------------------------------------------- #
def test_eligible_registered_only():
    assert eligible_positions("DEF", None) == ["DEF"]
    assert eligible_positions("DEF", "") == ["DEF"]


def test_eligible_same_registered_and_played_is_not_duplicated():
    assert eligible_positions("MID", "MID") == ["MID"]


def test_eligible_registered_then_played_when_different():
    # The Kimmich case: registered DEF, played MID -> can fill either slot.
    assert eligible_positions("DEF", "MID") == ["DEF", "MID"]


def test_eligible_registered_always_listed_first():
    assert eligible_positions("FWD", "MID")[0] == "FWD"


def test_eligible_unknown_registered_falls_back_to_played():
    assert eligible_positions(None, "MID") == ["MID"]
    assert eligible_positions("", "FWD") == ["FWD"]


def test_eligible_nothing_known():
    assert eligible_positions(None, None) == []
    assert eligible_positions("", "") == []


def test_eligible_normalises_free_text_inputs():
    assert eligible_positions("Centre Back", "MC") == ["DEF", "MID"]
    assert eligible_positions("Right Back", "Right Back") == ["DEF"]


# --------------------------------------------------------------------------- #
# position_score_map  — THE core rule
# --------------------------------------------------------------------------- #
def _score_fn(table):
    """Build a score_fn from a {pos: score} table, recording which positions it was
    asked to score."""
    calls = []

    def fn(pos):
        calls.append(pos)
        return table[pos]

    fn.calls = calls
    return fn


def test_score_always_from_registered_position_kimmich():
    # Listed DEF, played MID. DEF formula would give 40, MID formula 55.
    fn = _score_fn({"DEF": 40, "MID": 55})
    out = position_score_map("DEF", "MID", fn)
    # Both eligible slots carry the DEFENDER score, never the (higher) MID score.
    assert out == {"DEF": 40, "MID": 40}
    # And we only ever evaluated the registered (DEF) formula.
    assert fn.calls == ["DEF"]


def test_score_registered_only_when_played_same():
    fn = _score_fn({"MID": 33})
    assert position_score_map("MID", "MID", fn) == {"MID": 33}


def test_score_registered_only_when_played_unknown():
    fn = _score_fn({"FWD": 21})
    assert position_score_map("FWD", None, fn) == {"FWD": 21}


def test_score_reverse_case_registered_mid_played_def():
    # Symmetry: a registered MID who drops to DEF still scores his MID points,
    # and is eligible for a DEF slot too.
    fn = _score_fn({"MID": 60, "DEF": 25})
    out = position_score_map("MID", "DEF", fn)
    assert out == {"MID": 60, "DEF": 60}
    assert fn.calls == ["MID"]


def test_score_unknown_player_uses_played_position():
    # Not in the squad DB (no registered position) -> score at played position.
    fn = _score_fn({"FWD": 18})
    out = position_score_map(None, "FWD", fn)
    assert out == {"FWD": 18}
    assert fn.calls == ["FWD"]


def test_score_no_position_known_returns_empty():
    fn = _score_fn({})
    assert position_score_map(None, None, fn) == {}
    assert fn.calls == []  # never even tried to score


def test_score_map_accepts_free_text_positions():
    fn = _score_fn({"DEF": 12, "MID": 99})
    out = position_score_map("Centre Back", "Central Midfield", fn)
    assert out == {"DEF": 12, "MID": 12}


def test_score_negative_registered_score_still_applies_everywhere():
    # A red-carded defender can go negative; both slots reflect that same number.
    fn = _score_fn({"DEF": -7, "MID": 5})
    assert position_score_map("DEF", "MID", fn) == {"DEF": -7, "MID": -7}
