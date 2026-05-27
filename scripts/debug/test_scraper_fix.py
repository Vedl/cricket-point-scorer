from cricbuzz_scraper import CricbuzzScraper

def test_scraper():
    # URL known to have run-outs or at least to trigger parsing
    # Using the one from the user's screenshot if readable, or a generic one
    url = "https://www.cricbuzz.com/live-cricket-scorecard/121422/ind-vs-nz-5th-t20i-new-zealand-tour-of-india-2026"
    
    print(f"Testing scraper with URL: {url}")
    try:
        scraper = CricbuzzScraper()
        players = scraper.fetch_match_data(url)
        print(f"Successfully fetched {len(players)} players.")
        for p in players:
            if 'run_outs_direct' in p or 'run_outs_throw' in p:
                print(f"Run out stats found for {p['name']}: Direct={p.get('run_outs_direct',0)}, Throw={p.get('run_outs_throw',0)}")
    except Exception as e:
        print(f"Scraper failed: {e}")
        raise e

if __name__ == "__main__":
    test_scraper()
