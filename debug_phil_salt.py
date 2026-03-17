from cricbuzz_scraper import CricbuzzScraper

scraper = CricbuzzScraper()
url = "https://www.cricbuzz.com/live-cricket/scorecard/139175/eng-vs-sco-23rd-match-group-c-icc-mens-t20-world-cup-2026"
players = scraper.fetch_match_data(url)

print(f"\nTotal players: {len(players)}")
print("\n=== All Players ===")
for p in players:
    name = p.get('name', 'Unknown')
    role = p.get('role', 'Unknown')
    runs = p.get('runs', '-')
    catches = p.get('catches', 0)
    wickets = p.get('wickets', '-')
    print(f"  {name:25s} | Role: {role:15s} | Runs: {str(runs):4s} | Catches: {catches} | Wickets: {str(wickets):3s}")

# Check for duplicates
names = [p['name'] for p in players]
seen = set()
for n in names:
    if n.lower() in seen:
        print(f"\n*** DUPLICATE DETECTED: {n}")
    seen.add(n.lower())
    
# Check for near-duplicates
print("\n=== Checking Near-Duplicates ===")
for i, n1 in enumerate(names):
    for j in range(i+1, len(names)):
        n2 = names[j]
        n1_l = n1.lower()
        n2_l = n2.lower()
        if n1_l in n2_l or n2_l in n1_l:
            print(f"  Near-dup: '{n1}' <-> '{n2}'")
        # Also check word overlap
        w1 = set(n1_l.split())
        w2 = set(n2_l.split())
        if w1 & w2 and w1 != w2:
            print(f"  Word overlap: '{n1}' <-> '{n2}' (common: {w1 & w2})")
