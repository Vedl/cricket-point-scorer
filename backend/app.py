from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sys
import os

# Add parent directory to path to import existing modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cricbuzz_scraper import CricbuzzScraper
from player_score_calculator import CricketScoreCalculator

app = FastAPI(title="Cricket Points API")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ScoreRequest(BaseModel):
    url: str

@app.get("/api/calculate")
async def calculate_points(url: str):
    try:
        scraper = CricbuzzScraper()
        calculator = CricketScoreCalculator()
        
        print(f"Scraping URL: {url}")
        players_data = scraper.fetch_match_data(url)
        
        if not players_data:
            raise HTTPException(status_code=404, detail="No player data found or invalid URL")
            
        results = []
        for p in players_data:
            score = calculator.calculate_score(p)
            
            # Create a breakdown dict (simplified for now, logic is inside calculator)
            # To get a real breakdown, we'd need to refactor calculator to return a dict.
            # For now, we just return the total score and stats.
            
            p_result = {
                "name": p['name'],
                "role": p.get('role', 'Unknown'),
                "total_score": score,
                "stats": p,
                "breakdown": {} # Placeholder if we want detailed breakdown later
            }
            results.append(p_result)
            
        # Sort by score info
        results.sort(key=lambda x: x['total_score'], reverse=True)
        
        return {
            "match_info": "Match Scorecard", # Scraper doesn't extract match title yet, can add later
            "players": results
        }
        
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
