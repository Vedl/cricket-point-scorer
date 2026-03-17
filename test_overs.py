from player_score_calculator import CricketScoreCalculator

calc = CricketScoreCalculator()

def check_overs(overs_raw):
    print(f"--- Testing {overs_raw} ---")
    
    # Logic from _calculate_bowling
    if overs_raw > 0:
        o_int = int(overs_raw)
        # Simulate float precision issues
        o_dec = (overs_raw - o_int) * 10
        print(f"Raw Dec: {o_dec}")
        actual_overs = o_int + (o_dec / 6)
        print(f"Actual Overs (Current Logic): {actual_overs}")
        
        # Robust Logic
        o_dec_robust = round((overs_raw - o_int) * 10)
        actual_overs_robust = o_int + (o_dec_robust / 6)
        print(f"Actual Overs (Robust Logic): {actual_overs_robust}")
    
check_overs(3.3)
check_overs(3.5) # 3 overs 5 balls -> 3 + 5/6 = 3.833
check_overs(4.0)

# User Scenario: 3.3 -> 3.5 actual?
# 3.3 means 3 overs and 3 balls.
# 3 balls = 0.5 overs.
# Total = 3.5.
