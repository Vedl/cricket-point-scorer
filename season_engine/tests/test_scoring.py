"""Regression tests for the ported cricket score calculator.

Golden values pin the current scoring formula so future edits can't silently
change it. Also covers role normalisation and directional sanity.
"""

import pytest

from scoring import CricketScoreCalculator


@pytest.fixture
def calc():
    return CricketScoreCalculator()


@pytest.mark.parametrize(
    "stats,expected",
    [
        ({"role": "Batsman", "runs": 50, "balls_faced": 30, "fours": 5, "sixes": 2,
          "is_not_out": False}, 70),
        ({"role": "Bowler", "wickets": 3, "overs_bowled": 4, "maidens": 1,
          "runs_conceded": 24}, 89),
        ({"role": "Batsman", "runs": 0, "balls_faced": 3, "is_not_out": False}, -3),
        ({"role": "WK-Batsman", "runs": 20, "balls_faced": 15, "catches": 2,
          "stumpings": 1}, 37),
        ({"role": "Bowling Allrounder", "runs": 30, "balls_faced": 20, "sixes": 2,
          "wickets": 2, "overs_bowled": 4, "runs_conceded": 30}, 96),
    ],
)
def test_golden_scores(calc, stats, expected):
    assert calc.calculate_score(stats) == expected


def test_role_normalisation(calc):
    assert calc.normalize_role("WK") == "keeper"
    assert calc.normalize_role("Bowling Allrounder") == "bowl_ar"
    assert calc.normalize_role("Batting Allrounder") == "bat_ar"
    assert calc.normalize_role("") == "batsman"


def test_more_runs_scores_higher(calc):
    base = {"role": "Batsman", "balls_faced": 20, "is_not_out": False}
    assert calc.calculate_score({**base, "runs": 40}) > calc.calculate_score({**base, "runs": 10})


def test_wickets_add_points(calc):
    base = {"role": "Bowler", "overs_bowled": 4, "runs_conceded": 30}
    assert calc.calculate_score({**base, "wickets": 4}) > calc.calculate_score({**base, "wickets": 1})
