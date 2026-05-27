import pytest
from player_score_calculator import CricketScoreCalculator

@pytest.fixture
def calculator():
    return CricketScoreCalculator()

def test_batting_points_basic(calculator):
    stats = {
        'runs': 10,
        'balls_faced': 10,
        'fours': 0,
        'sixes': 0,
        'is_batter_or_allrounder': True
    }
    # 10 runs = 5 pts
    # SR 100 -> No points (70-130 neutral)
    assert calculator.calculate_score(stats) == 5.0

def test_batting_points_bonuses(calculator):
    stats = {
        'runs': 105, 
        'balls_faced': 50, # SR = 210 -> >170 -> +3
        'fours': 10, # +5 (10*0.5)
        'sixes': 5, # +5 (5*1)
        'is_batter_or_allrounder': True
    }
    # Runs: 105 * 0.5 = 52.5
    # Fours Bonus: 5
    # Sixes Bonus: 5
    # Milestone: 8 (for 100)
    # SR: 3
    # Total: 73.5
    assert calculator.calculate_score(stats) == 73.5

def test_duck_penalty(calculator):
    stats = {
        'runs': 0,
        'balls_faced': 1,
        'is_batter_or_allrounder': True
    }
    # Runs: 0
    # Penalty: -2
    # SR: N/A (<10 balls)
    # Total: -2
    assert calculator.calculate_score(stats) == -2.0

def test_bowling_points(calculator):
    stats = {
        'wickets': 5, # 5 * 12 = 60
        'maidens': 2, # 2 * 4 = 8
        'overs_bowled': 4.0,
        'runs_conceded': 10, # ER = 2.5 -> <5.00 -> +3
        'lbw_bowled_bonus': 3 # 3 * 4 = 12
    }
    # Wickets: 60
    # 5-wkt bonus: 12
    # Maidens: 8
    # LBW/Bowled: 12
    # ER: 3
    # Total: 95
    assert calculator.calculate_score(stats) == 95.0
    
def test_fielding_points(calculator):
    stats = {
        'catches': 3, # 3 * 4 = 12, +2 bonus = 14
        'stumpings': 1, # 6
        'run_outs_direct': 1, # 6
        'run_outs_throw': 1 # 3
    }
    # Total: 29
    assert calculator.calculate_score(stats) == 29.0

def test_economy_rate_negative(calculator):
    stats = {
        'overs_bowled': 4.0,
        'runs_conceded': 50, # ER = 12.5 -> >12 -> -3
        'wickets': 0
    }
    # ER: -3
    assert calculator.calculate_score(stats) == -3.0

def test_strike_rate_negative(calculator):
    stats = {
        'runs': 10,
        'balls_faced': 30, # SR = 33.33 -> <50 -> -3
        'is_batter_or_allrounder': True
    }
    # Runs: 10 * 0.5 = 5
    # SR: -3
    # Total: 2
    assert calculator.calculate_score(stats) == 2.0
