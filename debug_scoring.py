
from player_score_calculator import CricketScoreCalculator

calc = CricketScoreCalculator()

# Test case 1: Batting All-Rounder with 2 catches
stats_dar = {
    'role': 'Bowling Allrounder', 
    'runs': 0, 'balls_faced': 0, 'fours': 0, 'sixes': 0, 
    'wickets': 0, 'catches': 2
}
score_dar = calc.calculate_score(stats_dar)
print(f"Daryl Mitchell (bowl_ar, 2 catches): {score_dar} pts")

# Test case 2: Bowler with 0 catches
stats_sant = {
    'role': 'Bowler', 
    'wickets': 1, 'catches': 0, 'overs_bowled': 4.0, 'runs_conceded': 23
}
score_sant = calc.calculate_score(stats_sant)
print(f"Mitchell Santner (bowler, 1 wkt, 4-23): {score_sant} pts")

# Test case 3: Check normalize_role
roles = ['Batting Allrounder', 'Bowling Allrounder', 'Bowler', 'Use your brain', 'Allrounder']
for r in roles:
    print(f"Role '{r}' -> '{calc.normalize_role(r)}'")
