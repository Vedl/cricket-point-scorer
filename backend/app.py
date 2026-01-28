from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select
from typing import List
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import create_db_and_tables, get_session
from backend.models import Participant, Player, SquadPlayer, Match, PlayerScore
from cricbuzz_scraper import CricbuzzScraper
from player_score_calculator import CricketScoreCalculator

app = FastAPI(title="Cricket Auction Platform")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup():
    create_db_and_tables()

# --- Legacy Calculator Endpoint ---
@app.get("/api/calculate")
async def calculate_points(url: str):
    # ... (Keep existing logic if needed, or deprecate)
    # For now, let's keep it but ideally we move to the new system
    try:
        scraper = CricbuzzScraper()
        calculator = CricketScoreCalculator()
        print(f"Scraping URL: {url}")
        players_data = scraper.fetch_match_data(url)
        if not players_data:
            raise HTTPException(status_code=404, detail="No player data found")
        results = []
        for p in players_data:
            score = calculator.calculate_score(p)
            p_result = {
                "name": p['name'],
                "role": p.get('role', 'Unknown'),
                "total_score": score,
                "stats": p,
            }
            results.append(p_result)
        results.sort(key=lambda x: x['total_score'], reverse=True)
        return {"match_info": "Match Scorecard", "players": results}
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- Auction Platform Endpoints ---

@app.post("/api/participants", response_model=Participant)
def create_participant(participant: Participant, session: Session = Depends(get_session)):
    session.add(participant)
    session.commit()
    session.refresh(participant)
    return participant

@app.get("/api/participants", response_model=List[Participant])
def read_participants(session: Session = Depends(get_session)):
    return session.exec(select(Participant)).all()

@app.post("/api/val/add_to_squad")
def add_player_to_squad(participant_id: int, player_name: str, role: str, session: Session = Depends(get_session)):
    # 1. Check/Create Player
    player = session.exec(select(Player).where(Player.name == player_name)).first()
    if not player:
        player = Player(name=player_name, role=role)
        session.add(player)
        session.commit()
        session.refresh(player)
    
    # 2. Add to Squad
    squad_entry = SquadPlayer(participant_id=participant_id, player_id=player.id)
    session.add(squad_entry)
    session.commit()
    return {"message": f"Added {player_name} to participant {participant_id}"}
    
@app.post("/api/admin/set_ir")
def set_injury_reserve(participant_id: int, player_id: int, is_ir: bool, session: Session = Depends(get_session)):
    entry = session.exec(select(SquadPlayer).where(
        SquadPlayer.participant_id == participant_id,
        SquadPlayer.player_id == player_id
    )).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Player not in squad")
    
    entry.is_ir = is_ir
    session.add(entry)
    session.commit()
    return {"message": "Updated IR status"}

from pydantic import BaseModel
class GameweekRequest(BaseModel):
    gameweek: int
    match_urls: List[str]

from backend.engine import GameweekProcessor

@app.post("/api/gameweek/process")
def process_gameweek(request: GameweekRequest, session: Session = Depends(get_session)):
    processor = GameweekProcessor(session)
    
    # Process all matches
    for url in request.match_urls:
        processor.process_match_url(url, request.gameweek)
        
    # Calculate Leaderboard
    leaderboard = processor.calculate_leaderboard(request.gameweek)
    
    return {"gameweek": request.gameweek, "leaderboard": leaderboard}

@app.get("/api/leaderboard/cumulative")
def get_cumulative_leaderboard(session: Session = Depends(get_session)):
    processor = GameweekProcessor(session)
    return processor.calculate_cumulative_leaderboard()

@app.get("/api/leaderboard/{gameweek}")
def get_gameweek_leaderboard(gameweek: int, session: Session = Depends(get_session)):
    processor = GameweekProcessor(session)
    return processor.calculate_leaderboard(gameweek)
