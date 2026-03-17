from player_score_calculator import CricketScoreCalculator

calc = CricketScoreCalculator()

# Sherfane Rutherford Stats
stats = {
    'role': 'batsman', # Assuming he is listed as batsman
    'runs': 76,
    'balls_faced': 42,
    'fours': 2,
    'sixes': 7,
    'is_not_out': True,
    'wickets': 0,
    'catches': 0
}

breakdown = calc.get_score_breakdown(stats)
print(f"Role: {breakdown['role']}")
print(f"Total Score: {breakdown['total']}")
print("-" * 20)
print("Breakdown:")
print(f"Batting Points: {breakdown['batting_points']}")

# Manual Verification of Parts
pts = 0
run_mult = 0.5 # Batsman
pts += 76 * run_mult
print(f"Runs ({76} * {run_mult}): {76 * run_mult}")

four_pts = 2
pts += 2 * four_pts
print(f"4s ({2} * {four_pts}): {2 * four_pts}")

six_pts = 4
pts += 7 * six_pts
print(f"6s ({7} * {six_pts}): {7 * six_pts}")

sr = (76/42)*100
sr_bonus = sr / 10 # balls > 10
pts += sr_bonus
print(f"SR Bonus ({sr:.2f} / 10): {sr_bonus:.2f}")

not_out_bonus = 20 # balls > 40
pts += not_out_bonus
print(f"Not Out Bonus (>40 balls): {not_out_bonus}")

milestone = 10 # 50 runs
pts += milestone
print(f"Milestone (50 runs): {milestone}")

print(f"Calculated Sum: {pts}")
print(f"Rounded: {round(pts)}")
