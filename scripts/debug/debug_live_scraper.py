"""
Debug script to test the actual scraper against the NZ vs UAE match URL.
This will show exactly what stats are parsed for Glenn Phillips.
"""
from cricbuzz_scraper import CricbuzzScraper
from player_score_calculator import CricketScoreCalculator

URL = "https://www.cricbuzz.com/live-cricket-scorecard/139062/nz-vs-uae-11th-match-group-d-icc-mens-t20-world-cup-2026"

scraper = CricbuzzScraper()
calculator = CricketScoreCalculator()

print("=== Fetching match data ===")
players = scraper.fetch_match_data(URL)

print(f"\n=== {len(players)} players found ===\n")

# Focus on Glenn Phillips
for p in players:
    name = p.get('name', '')
    if 'glenn' in name.lower() or 'phillips' in name.lower():
        print(f"*** GLENN PHILLIPS FOUND ***")
        print(f"  Full stats dict: {p}")
        score = calculator.calculate_score(p)
        breakdown = calculator.get_score_breakdown(p)
        print(f"  Score: {score}")
        print(f"  Breakdown: {breakdown}")
        print()

# Also show ALL players with catches
print("\n=== ALL PLAYERS WITH CATCHES ===")
for p in players:
    catches = p.get('catches', 0)
    if catches and catches > 0:
        score = calculator.calculate_score(p)
        print(f"  {p['name']}: catches={catches}, score={score}, role={p.get('role', '?')}")

# Show full leaderboard
print("\n=== FULL LEADERBOARD ===")
results = []
for p in players:
    score = calculator.calculate_score(p)
    results.append({
        "Player": p['name'],
        "Role": p.get('role', 'Unknown'),
        "Points": score,
        "Runs": p.get('runs', 0),
        "Wickets": p.get('wickets', 0),
        "Catches": p.get('catches', 0),
        "Overs": p.get('overs_bowled', 0),
        "Runs_Conceded": p.get('runs_conceded', 0),
    })

results.sort(key=lambda x: x['Points'], reverse=True)
for r in results:
    print(f"  {r['Player']:25s} | Role: {r['Role']:22s} | Pts: {r['Points']:4d} | R: {r['Runs'] or 0:3d} | W: {r['Wickets'] or 0} | C: {r['Catches'] or 0} | Ov: {r['Overs'] or 0} | RC: {r['Runs_Conceded'] or 0}")
