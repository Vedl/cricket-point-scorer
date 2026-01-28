from player_score_calculator import CricketScoreCalculator
from cricbuzz_scraper import CricbuzzScraper
import sys

def main():
    print("--- Fantasy Cricket Points Calculator (Deflated Version) ---\n")
    
    url = input("Enter Cricbuzz Scorecard URL: ").strip()
    if not url:
        print("No URL provided. Exiting.")
        return

    print(f"\nFetching data from: {url} ...")
    
    scraper = CricbuzzScraper()
    players_stats = scraper.fetch_match_data(url)
    
    if not players_stats:
        print("No player data found. Please check the URL (should be a scorecard link).")
        return
        
    calculator = CricketScoreCalculator()
    
    scores = []
    for p in players_stats:
        score = calculator.calculate_score(p)
        scores.append((p['name'], score, p))
        
    # Sort by score descending
    scores.sort(key=lambda x: x[1], reverse=True)
    
    print(f"\n{'Player':<25} | {'Score':<6} | {'Brief Stats'}")
    print("-" * 60)
    
    for name, score, stats in scores:
        summary = []
        if stats.get('runs', 0) > 0: summary.append(f"{stats['runs']} run")
        if stats.get('wickets', 0) > 0: summary.append(f"{stats['wickets']} wkt")
        if stats.get('catches', 0) > 0: summary.append(f"{stats['catches']} ct")
        
        stats_str = ", ".join(summary)
        print(f"{name:<25} | {score:<6.1f} | {stats_str}")

if __name__ == "__main__":
    main()
