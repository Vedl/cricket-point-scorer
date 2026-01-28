from player_score_calculator import CricketScoreCalculator
from cricbuzz_scraper import CricbuzzScraper

def verify_match(url, match_name):
    print(f"\n=== Verifying: {match_name} ===")
    print(f"URL: {url}")
    
    scraper = CricbuzzScraper()
    calculator = CricketScoreCalculator()
    
    players = scraper.fetch_match_data(url)
    if not players:
        print("Failed to fetch data.")
        return

    scores = []
    for p in players:
        score = calculator.calculate_score(p)
        scores.append((p['name'], score, p))
    
    scores.sort(key=lambda x: x[1], reverse=True)
    
    print(f"{'Player':<25} | {'Role':<15} | {'Score':<6} | {'Stats'}")
    print("-" * 80)
    for name, score, stats in scores[:10]: # Top 10
        summary = []
        if stats.get('runs', 0): summary.append(f"{stats['runs']} runs")
        if stats.get('wickets', 0): summary.append(f"{stats['wickets']} wkts")
        if stats.get('catches', 0): summary.append(f"{stats['catches']} ct")
        print(f"{name:<25} | {stats.get('role', 'N/A')[:15]:<15} | {score:<6.1f} | {', '.join(summary)}")

def main():
    matches = [
        (
            "https://www.cricbuzz.com/live-cricket-scorecard/141936/banw-vs-thaiw-21st-match-super-six-icc-womens-t20-world-cup-global-qualifier-2026",
            "BANW vs THAIW (Recent T20)"
        ),
        (
            "https://www.cricbuzz.com/live-cricket-scorecard/141958/usaw-vs-nedw-23rd-match-super-six-icc-womens-t20-world-cup-global-qualifier-2026",
            "USAW vs NEDW (Recent T20)"
        ),
        (
            "https://www.cricbuzz.com/live-cricket-scorecard/141947/scow-vs-irew-22nd-match-super-six-icc-womens-t20-world-cup-global-qualifier-2026",
            "SCOW vs IREW (Recent T20)"
        )
    ]
    
    for url, name in matches:
        verify_match(url, name)

if __name__ == "__main__":
    main()
