from player_score_calculator import CricketScoreCalculator

calc = CricketScoreCalculator()

# Dipendra Singh Airee Stats (from screenshots)
# Role assumption: Batting All-Rounder (bat_ar)
# Changing role to see variations if needed.
roles_to_test = ['bat_ar', 'bowl_ar', 'batsman']

for role in roles_to_test:
    print(f"\n--- Testing Role: {role} ---")
    stats = {
        'role': role,
        'runs': 17,
        'balls_faced': 18,
        'fours': 0,
        'sixes': 0,
        'is_not_out': False,
        
        # Bowling
        'overs_bowled': 3.4, # Should be converted to 3.6666
        'maidens': 0,
        'runs_conceded': 24,
        'wickets': 0,
        'catches': 0
    }

    breakdown = calc.get_score_breakdown(stats)
    print(f"Total Score: {breakdown['total']}")
    print(f"Batting Pts: {breakdown['batting_points']}")
    print(f"Bowling Pts: {breakdown['bowling_points']}")
    print(f"Fielding Pts: {breakdown['fielding_points']}")
    
    # Check economy calc
    overs_raw = 3.4
    o_int = int(overs_raw)
    o_dec = round((overs_raw - o_int) * 10)
    actual_overs = o_int + (o_dec / 6)
    econ = 24 / actual_overs if actual_overs > 0 else 0
    print(f"Debug Econ: {econ:.3f} (Runs: 24, Overs: {actual_overs:.3f})")
