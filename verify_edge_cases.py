from player_score_calculator import CricketScoreCalculator

def test_edge_cases():
    calc = CricketScoreCalculator()
    
    print("=== Verification: Edge Cases & High Scores ===\n")

    # Case 1: The "Finisher" Edge Case
    # 1 ball, 6 runs (SR 600). Should NOT get SR bonus if min balls > 1.
    finisher = {
        'name': 'Finisher',
        'role': 'Batsman',
        'runs': 6,
        'balls_faced': 1,
        'fours': 0,
        'sixes': 1,
        'is_batter_or_allrounder': True
    }
    score_finisher = calc.calculate_score(finisher)
    print(f"Case 1: 1 Ball, 6 Runs (SR 600)")
    print(f"  Score: {score_finisher}")
    print(f"  Expected: 4. No SR bonus.")
    print(f"  Status: {'PASS' if score_finisher == 4 else 'FAIL'}\n")

    # Case 2: High Scoring IPL Innings (Head/Abhishek style)
    # 80 runs off 24 balls (SR 333). 
    tm_head = {
        'name': 'Travis Head',
        'role': 'Batsman',
        'runs': 80,
        'balls_faced': 24,
        'fours': 8,
        'sixes': 6,
        'is_batter_or_allrounder': True
    }
    score_head = calc.calculate_score(tm_head)
    print(f"Case 2: High Scorer (80 runs off 24 balls)")
    print(f"  Breakdown:")
    print(f"    Runs (0.5): 40.0")
    print(f"    Fours (0.5): 4.0")
    print(f"    Sixes (1.0): 6.0")
    print(f"    50 Bonus: 4.0")
    print(f"    30 Bonus: 2.0")
    print(f"    SR Bonus (>250): 5.0")
    expected_head = 61
    print(f"  Score: {score_head}")
    print(f"  Expected: {expected_head}")
    print(f"  Status: {'PASS' if score_head == expected_head else 'FAIL'}\n")

    # Case 3: High Scoring Century (But Slow?)
    # 100 runs off 70 balls (SR 142).
    centurion = {
        'name': 'Anchor',
        'role': 'Batsman',
        'runs': 100,
        'balls_faced': 70,
        'fours': 10,
        'sixes': 2,
        'is_batter_or_allrounder': True
    }
    score_cent = calc.calculate_score(centurion)
    print(f"Case 3: Century (SR 142)")
    print(f"  Breakdown:")
    print(f"    Runs: 50.0")
    print(f"    Boundaries: 5 + 2 = 7.0")
    print(f"    Bonuses (30/50/100): 2+4+8 = 14.0")
    print(f"    SR Bonus (130-150): 1.0")
    expected_cent = 72
    print(f"  Score: {score_cent}")
    print(f"  Expected: {expected_cent}")
    print(f"  Status: {'PASS' if score_cent == expected_cent else 'FAIL'}\n")
    
    # Case 4: Bowler with Duck (Exempt check)
    bowler_duck = {
        'name': 'Tailender',
        'role': 'Bowler',
        'runs': 0,
        'balls_faced': 5,
        'is_batter_or_allrounder': False
    }
    score_bd = calc.calculate_score(bowler_duck)
    print(f"Case 4: Bowler Duck")
    print(f"  Score: {score_bd}")
    print(f"  Expected: 0 (Exempt from -2)")
    print(f"  Status: {'PASS' if score_bd == 0 else 'FAIL'}\n")

if __name__ == "__main__":
    test_edge_cases()
