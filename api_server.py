"""
FastAPI wrapper around the existing Cricket Auction Platform.

Wraps existing modules (CricbuzzScraper, CricketScoreCalculator) without
rewriting business logic. Talks to the same Firebase Realtime Database
that the Streamlit app uses.

Usage:
    uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload
"""

import os
import json
import random
import string
import hashlib
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Literal, Any
import csv
import io

import requests as http_requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator

# --- Import existing project modules (no rewriting) ---
from cricbuzz_scraper import CricbuzzScraper
from player_score_calculator import CricketScoreCalculator

# =========================================================
# Firebase Config (same DB as the Streamlit app)
# =========================================================
FIREBASE_URL = os.environ.get(
    "FIREBASE_DATABASE_URL",
    "https://cricket-auction-b00e2-default-rtdb.asia-southeast1.firebasedatabase.app",
)
AUCTION_ENDPOINT = f"{FIREBASE_URL}/auction_data.json"

IST = timezone(timedelta(hours=5, minutes=30))


def _get_ist_now() -> datetime:
    return datetime.now(IST)


# =========================================================
# Lightweight Firebase helpers (mirrors StorageManager logic
# without the Streamlit dependency)
# =========================================================
def _normalize_firebase_data(data):
    """
    Firebase converts dicts with numeric keys to sparse arrays.
    Mirrors StorageManager._normalize_firebase_data.
    """
    if data is None:
        return {}
    if isinstance(data, dict):
        return {k: _normalize_firebase_data(v) for k, v in data.items()}
    if isinstance(data, list):
        if any(item is None for item in data):
            # Sparse array → convert back to dict
            return {
                str(i): _normalize_firebase_data(item)
                for i, item in enumerate(data)
                if item is not None
            }
        return [
            _normalize_firebase_data(item) if isinstance(item, (dict, list)) else item
            for item in data
        ]
    return data


def _firebase_get(path: str = "") -> dict:
    """GET from Firebase.  `path` is optional sub-path under auction_data."""
    url = f"{FIREBASE_URL}/auction_data{path}.json"
    try:
        resp = http_requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json() or {}
        return _normalize_firebase_data(data)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Firebase read failed: {e}")


def _firebase_put(data, path: str = "") -> None:
    """PUT to Firebase.  `path` is optional sub-path under auction_data."""
    url = f"{FIREBASE_URL}/auction_data{path}.json"
    try:
        resp = http_requests.put(
            url,
            json=data,
            headers={"Content-Type": "application/json"},
            timeout=15,
        )
        resp.raise_for_status()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Firebase write failed: {e}")


def _firebase_patch(data: dict, path: str = "") -> None:
    """PATCH (partial update) to Firebase."""
    url = f"{FIREBASE_URL}/auction_data{path}.json"
    try:
        resp = http_requests.patch(
            url,
            json=data,
            headers={"Content-Type": "application/json"},
            timeout=15,
        )
        resp.raise_for_status()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Firebase patch failed: {e}")


# =========================================================
# Pydantic request / response models
# =========================================================
class BidRequest(BaseModel):
    room_code: str
    participant_name: str
    player_name: str
    amount: int

class ImportCsvRequest(BaseModel):
    room_code: str
    admin_name: str
    csv_text: str


class AuthLoginRequest(BaseModel):
    username: str
    password: str


class AuthRegisterRequest(BaseModel):
    username: str
    password: str


class AuctionStartRequest(BaseModel):
    room_code: str
    admin_name: str
    deadline_hours: Optional[float] = 24.0


class CreateRoomRequest(BaseModel):
    admin_name: str
    tournament_type: Literal["t20_wc", "ipl"]
    user_id: Optional[str] = None  # If provided, auto-link uid to admin
    admin_playing: bool = True

    @field_validator("admin_name")
    @classmethod
    def admin_name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("admin_name must not be empty")
        return v.strip()


class JoinRoomRequest(BaseModel):
    room_code: str
    participant_name: str
    user_id: Optional[str] = None  # If provided, auto-link uid to participant
    team_name: Optional[str] = None  # Required for IPL rooms (franchise claim)

    @field_validator("participant_name")
    @classmethod
    def participant_name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("participant_name must not be empty")
        return v.strip()


class ClaimTeamRequest(BaseModel):
    """Claim an IPL franchise team in a room."""
    room_code: str
    participant_name: str
    team_name: str  # e.g. "CSK", "MI", "RCB"

    @field_validator("team_name")
    @classmethod
    def team_name_valid(cls, v: str) -> str:
        v = v.strip().upper()
        if v not in IPL_TEAMS:
            raise ValueError(f"Invalid team. Must be one of: {', '.join(sorted(IPL_TEAMS))}")
        return v


class TradeProposalRequest(BaseModel):
    """Submit a trade proposal between two participants."""
    room_code: str
    from_participant: str
    to_participant: str
    trade_type: Literal["Transfer (Sell)", "Transfer (Buy)", "Exchange", "Loan Out", "Loan In"]
    player: Optional[str] = None       # For Sell/Buy/Loan
    give_player: Optional[str] = None  # For Exchange
    get_player: Optional[str] = None   # For Exchange
    price: float = 0
    user_id: Optional[str] = None


class TradeRespondRequest(BaseModel):
    """Accept or reject a trade proposal."""
    room_code: str
    trade_id: str
    participant_name: str
    action: Literal["accept", "reject"]
    user_id: Optional[str] = None


class TradeAdminRequest(BaseModel):
    """Admin approve/reject a pending_admin trade."""
    room_code: str
    trade_id: str
    admin_name: str
    action: Literal["approve", "reject"]


class TradeForceRequest(BaseModel):
    """Admin force-execute a trade."""
    room_code: str
    admin_name: str
    sender_name: str
    receiver_name: str
    player_name: str
    price: float = 0


class BoostRequest(BaseModel):
    """Admin grants one-time 100M boost."""
    room_code: str
    admin_name: str


class LockSquadsRequest(BaseModel):
    """Admin locks squads for current GW."""
    room_code: str
    admin_name: str


class AdvanceGameweekRequest(BaseModel):
    """Admin advances to next GW and reopens market."""
    room_code: str
    admin_name: str


class ReleasePlayerRequest(BaseModel):
    """Release a player from squad."""
    room_code: str
    participant_name: str
    player_name: str
    user_id: Optional[str] = None


class SetDeadlineRequest(BaseModel):
    """Admin sets bidding deadline for current GW."""
    room_code: str
    admin_name: str
    deadline_iso: str  # ISO datetime string e.g. '2026-03-28T18:00:00+05:30'


class SetInjuryReserveRequest(BaseModel):
    """Participant sets their injury reserve player."""
    room_code: str
    participant_name: str
    player_name: str
    user_id: Optional[str] = None


class EliminateRequest(BaseModel):
    """Admin triggers elimination after a GW."""
    room_code: str
    admin_name: str


class CalculateScoresRequest(BaseModel):
    """Admin calculates GW scores from a Cricbuzz URL."""
    room_code: str
    admin_name: str
    cricbuzz_url: str
    gameweek: Optional[int] = None  # defaults to current_gameweek


class ImportSquadsRequest(BaseModel):
    """Admin imports squads for all participants with claim codes."""
    room_code: str
    admin_name: str
    squads: dict  # {participant_name: [{name, role, team, buy_price}]}
    budgets: Optional[dict] = None  # {participant_name: remaining_budget}


class GenerateClaimTokenRequest(BaseModel):
    """Only the room admin may generate claim tokens."""
    room_code: str
    participant_name: str
    admin_name: str


class LinkParticipantRequest(BaseModel):
    """Link a Firebase Auth uid to an existing participant using a claim token."""
    room_code: str
    participant_name: str
    claim_token: str
    uid: str

    @field_validator("uid", "claim_token")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Field must not be empty")
        return v.strip()


# =========================================================
# Response models (for Swagger / OpenAPI docs)
# =========================================================
class ClaimTokenResponse(BaseModel):
    claim_token: str
    expires: str
    participant_name: str
    room_code: str


class LinkParticipantResponse(BaseModel):
    linked: bool
    room_code: str
    participant_name: str
    uid: str


class UserRoomEntry(BaseModel):
    room_code: str
    participant_name: str
    tournament_type: str
    game_phase: str
    admin: str
    role: str
    is_admin: bool
    participant_count: int
    created_at: Optional[str] = None


class UserRoomsResponse(BaseModel):
    uid: str
    display_name: str
    rooms: List[UserRoomEntry]


class PlayerEntry(BaseModel):
    name: str
    role: str
    team: str
    base_price: int


class PlayersResponse(BaseModel):
    players: List[PlayerEntry]
    total: int


# =========================================================
# FastAPI app
# =========================================================
app = FastAPI(
    title="Cricket Auction API",
    description="REST wrapper around the Cricket Auction Platform — reads/writes the same Firebase DB as the Streamlit app.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Singleton instances of existing modules
scraper = CricbuzzScraper()
calculator = CricketScoreCalculator()

# Default starting budget per tournament type
_DEFAULT_BUDGET = {"t20_wc": 200, "ipl": 1000}

# IPL 2026 franchise teams
IPL_TEAMS = {
    "CSK": "Chennai Super Kings",
    "MI": "Mumbai Indians",
    "RCB": "Royal Challengers Bengaluru",
    "KKR": "Kolkata Knight Riders",
    "SRH": "Sunrisers Hyderabad",
    "DC": "Delhi Capitals",
    "PBKS": "Punjab Kings",
    "RR": "Rajasthan Royals",
    "GT": "Gujarat Titans",
    "LSG": "Lucknow Super Giants",
}

# Tournament catalogue (static, returned by GET /tournaments)
_TOURNAMENTS = [
    {
        "id": "ipl",
        "name": "TATA IPL 2026",
        "sport": "cricket",
        "status": "active",
        "description": "Indian Premier League 2026 – 10 teams, 84 matches",
        "start_date": "2026-03-28",
        "end_date": "2026-05-31",
        "icon": "🏏",
        "teams": list(IPL_TEAMS.keys()),
        "total_gameweeks": 13,
    },
    {
        "id": "t20_wc",
        "name": "ICC T20 World Cup 2026",
        "sport": "cricket",
        "status": "archived",
        "description": "T20 World Cup 2026 India & Sri Lanka – Concluded",
        "start_date": "2026-02-07",
        "end_date": "2026-03-08",
        "icon": "🏆",
        "teams": [],
        "total_gameweeks": 9,
    },
    {
        "id": "ucl_26_27",
        "name": "UEFA Champions League 2026/27",
        "sport": "football",
        "status": "upcoming",
        "description": "Champions League 2026/27 – Coming Soon",
        "start_date": "2026-09-01",
        "end_date": "2027-06-01",
        "icon": "⚽",
        "teams": [],
        "total_gameweeks": 0,
    },
    {
        "id": "fifa_wc_2026",
        "name": "FIFA World Cup 2026",
        "sport": "football",
        "status": "upcoming",
        "description": "FIFA World Cup 2026 USA, Canada & Mexico – Coming Soon",
        "start_date": "2026-06-11",
        "end_date": "2026-07-19",
        "icon": "🌍",
        "teams": [],
        "total_gameweeks": 0,
    },
]


def _generate_room_code(length: int = 6) -> str:
    """Generate a random alphanumeric room code (uppercase)."""
    chars = string.ascii_uppercase + string.digits
    return "".join(random.choices(chars, k=length))


def _generate_claim_token(length: int = 10) -> str:
    """Generate a random single-use claim token (mixed case + digits)."""
    chars = string.ascii_letters + string.digits
    return "".join(random.choices(chars, k=length))


def _auto_link_uid(data: dict, room_code: str, participant_name: str,
                   user_id: str, is_admin: bool) -> None:
    """
    Auto-link a uid → participant_name in room_user_map and users/{uid}.
    Mutates `data` in place (caller must persist).
    Raises HTTPException 409 if participant is already linked to a *different* uid.
    """
    room_user_map = data.setdefault("room_user_map", {})
    room_map = room_user_map.setdefault(room_code, {})

    existing_uid = room_map.get(participant_name)
    if existing_uid and existing_uid != user_id:
        raise HTTPException(
            status_code=409,
            detail=f"Participant '{participant_name}' is already linked to another account",
        )

    room_map[participant_name] = user_id

    users = data.setdefault("users", {})
    profile = users.setdefault(user_id, {})
    profile["display_name"] = participant_name
    user_rooms = profile.setdefault("rooms", {})
    user_rooms[room_code] = participant_name  # value = participant name for lookup


# ----------------------------------------------------------
# Custom Auth API (Streamlit compatibility)
# ----------------------------------------------------------
@app.post("/auth/login", tags=["Auth"])
async def auth_login(req: AuthLoginRequest):
    data = _firebase_get()
    users = data.get("users", {})
    
    if req.username not in users:
        raise HTTPException(status_code=404, detail="Username not found.")
        
    stored_hash = users[req.username].get("password_hash", "")
    provided_hash = hashlib.sha256(req.password.encode()).hexdigest()
    
    if not stored_hash or stored_hash != provided_hash:
        raise HTTPException(status_code=401, detail="Incorrect password.")
        
    return {
        "success": True, 
        "uid": req.username,  # In this system, username is the unique identifier
        "username": req.username
    }


@app.post("/auth/register", tags=["Auth"])
async def auth_register(req: AuthRegisterRequest):
    if len(req.password) < 4:
        raise HTTPException(status_code=400, detail="Password must be at least 4 characters.")
        
    data = _firebase_get()
    users = data.get("users", {})
    
    if req.username in users:
        raise HTTPException(status_code=400, detail="Username already exists. Please choose another.")
        
    pwd_hash = hashlib.sha256(req.password.encode()).hexdigest()
    
    # Save back directly. We use _firebase_patch to update just this user safely.
    _firebase_patch({"password_hash": pwd_hash}, path=f"/users/{req.username}")
    
    return {
        "success": True, 
        "uid": req.username,
        "username": req.username
    }


# ----------------------------------------------------------
# 0. GET /
# ----------------------------------------------------------
@app.get("/")
async def root():
    return {
        "message": "Cricket Auction API is Live!",
        "docs_url": "/docs",
        "health_check": "/health"
    }


# ----------------------------------------------------------
# 1.  GET /health
# ----------------------------------------------------------
@app.get("/health")
async def health():
    """Basic liveness + Firebase connectivity check."""
    firebase_ok = False
    try:
        resp = http_requests.get(f"{FIREBASE_URL}/.json?shallow=true", timeout=5)
        firebase_ok = resp.status_code == 200
    except Exception:
        pass
    return {
        "status": "ok",
        "timestamp": _get_ist_now().isoformat(),
        "firebase_connected": firebase_ok,
    }


# ----------------------------------------------------------
# 1a.  GET /tournaments
# ----------------------------------------------------------
@app.get("/tournaments")
async def list_tournaments():
    """Returns the list of available tournaments with status.
    
    Status values:
    - active: Can create/join rooms
    - archived: Can still create/join rooms (shown in Archived section)
    - upcoming: Cannot create rooms (greyed out)
    """
    return {"tournaments": _TOURNAMENTS}


# ----------------------------------------------------------
# 2.  POST /auction/create-room
# ----------------------------------------------------------
@app.post("/auction/create-room")
async def create_room(req: CreateRoomRequest):
    """
    Creates a new auction room with a random 6-character code.
    The creator becomes the admin and the first participant.
    Participants remain as a LIST to preserve Streamlit compatibility.

    If `user_id` is provided, auto-links the uid to the admin participant.

    Example:
        curl -X POST http://localhost:8000/auction/create-room \
          -H 'Content-Type: application/json' \
          -d '{"admin_name": "Alice", "tournament_type": "ipl", "user_id": "firebase_uid_123"}'
    """
    data = _firebase_get()
    rooms = data.get("rooms", {})

    # Generate a unique room code (retry on collisions)
    room_code = _generate_room_code()
    while room_code in rooms:
        room_code = _generate_room_code()

    now = _get_ist_now()
    budget = _DEFAULT_BUDGET.get(req.tournament_type, 200)

    room = {
        "admin": req.admin_name,
        "admin_playing": req.admin_playing,
        "tournament_type": req.tournament_type,
        "created_at": now.isoformat(),
        "game_phase": "NotStarted",
        "tournament_phase": "league" if req.tournament_type == "ipl" else "super8",
        "current_gameweek": 1,
        "squads_locked": False,
        "active_bids": [],
        "participants": [],
    }
    
    if req.admin_playing:
        room["participants"].append({
            "name": req.admin_name,
            "budget": budget,
            "squad": [],
            "eliminated": False,
        })

    # IPL-specific room fields
    if req.tournament_type == "ipl":
        room["ipl_teams"] = list(IPL_TEAMS.keys())
        room["claimed_teams"] = {}  # {participant_name: team_code}

    rooms[room_code] = room
    data["rooms"] = rooms

    # Auto-link uid if provided
    if req.user_id and req.user_id.strip():
        _auto_link_uid(data, room_code, req.admin_name, req.user_id.strip(), is_admin=True)

    _firebase_put(data)

    return {
        "room_code": room_code,
        "admin_name": req.admin_name,
        "tournament_type": req.tournament_type,
    }


# ----------------------------------------------------------
# 3.  POST /auction/join-room
# ----------------------------------------------------------
@app.post("/auction/join-room")
async def join_room(req: JoinRoomRequest):
    """
    Adds a new participant to an existing room.
    - Room must exist
    - Name must be unique within the room
    - Cannot join if game_phase == 'Bidding'

    If `user_id` is provided, auto-links the uid to the new participant.

    Example:
        curl -X POST http://localhost:8000/auction/join-room \
          -H 'Content-Type: application/json' \
          -d '{"room_code": "ABC123", "participant_name": "Bob", "user_id": "uid_456"}'
    """
    data = _firebase_get()
    rooms = data.get("rooms", {})
    room = rooms.get(req.room_code)
    if not room:
        raise HTTPException(status_code=404, detail=f"Room '{req.room_code}' not found")

    # Cannot join during active bidding
    if room.get("game_phase") == "Bidding":
        raise HTTPException(
            status_code=403,
            detail="Cannot join a room while bidding is in progress",
        )

    # Check for duplicate name
    existing_names = {p.get("name") for p in room.get("participants", [])}
    if req.participant_name in existing_names:
        raise HTTPException(
            status_code=409,
            detail=f"Name '{req.participant_name}' is already taken in this room",
        )

    # Add participant with correct budget for the tournament type
    tournament_type = room.get("tournament_type", "t20_wc")
    budget = _DEFAULT_BUDGET.get(tournament_type, 200)

    participants = room.get("participants", [])
    new_participant = {
        "name": req.participant_name,
        "budget": budget,
        "squad": [],
        "eliminated": False,
    }
    participants.append(new_participant)
    room["participants"] = participants

    # IPL team claiming on join (optional — can also use POST /auction/claim-team)
    if req.team_name and tournament_type == "ipl":
        team_code = req.team_name.strip().upper()
        if team_code not in IPL_TEAMS:
            raise HTTPException(status_code=400, detail=f"Invalid IPL team '{team_code}'")
        claimed = room.get("claimed_teams", {})
        # Check if team is already taken
        if team_code in claimed.values():
            owner = next(k for k, v in claimed.items() if v == team_code)
            raise HTTPException(
                status_code=409,
                detail=f"Team '{team_code}' is already claimed by '{owner}'",
            )
        claimed[req.participant_name] = team_code
        room["claimed_teams"] = claimed

    # Auto-link uid if provided
    if req.user_id and req.user_id.strip():
        _auto_link_uid(data, req.room_code, req.participant_name, req.user_id.strip(), is_admin=False)

    _firebase_put(data)

    # Return updated state (reuse the auction_state logic)
    return await auction_state(room_code=req.room_code)


# ----------------------------------------------------------
# 3b.  POST /auction/claim-team
# ----------------------------------------------------------
@app.post("/auction/claim-team")
async def claim_team(req: ClaimTeamRequest):
    """
    Claims an IPL franchise team for a participant in a room.
    Once claimed, the team cannot be changed.

    Only works for IPL rooms. Each team can only be claimed by one participant.

    Example:
        curl -X POST http://localhost:8000/auction/claim-team \\
          -H 'Content-Type: application/json' \\
          -d '{"room_code": "ABC123", "participant_name": "Bob", "team_name": "CSK"}'
    """
    data = _firebase_get()
    rooms = data.get("rooms", {})
    room = rooms.get(req.room_code)
    if not room:
        raise HTTPException(status_code=404, detail=f"Room '{req.room_code}' not found")

    if room.get("tournament_type") != "ipl":
        raise HTTPException(
            status_code=400, detail="Team claiming is only available for IPL rooms"
        )

    # Verify participant exists
    participants = room.get("participants", [])
    p_exists = any(p.get("name") == req.participant_name for p in participants)
    if not p_exists:
        raise HTTPException(
            status_code=404,
            detail=f"Participant '{req.participant_name}' not found in room '{req.room_code}'",
        )

    claimed = room.get("claimed_teams", {})

    # Check if participant already claimed a team (locked once claimed)
    if req.participant_name in claimed:
        raise HTTPException(
            status_code=409,
            detail=f"You have already claimed '{IPL_TEAMS.get(claimed[req.participant_name], claimed[req.participant_name])}'. Team claims are locked once made.",
        )

    # Check if team is already taken
    if req.team_name in claimed.values():
        owner = next(k for k, v in claimed.items() if v == req.team_name)
        raise HTTPException(
            status_code=409,
            detail=f"'{IPL_TEAMS[req.team_name]}' is already claimed by '{owner}'",
        )

    # Claim the team
    claimed[req.participant_name] = req.team_name
    room["claimed_teams"] = claimed
    _firebase_put(data)

    return {
        "message": f"Team '{IPL_TEAMS[req.team_name]}' claimed successfully",
        "room_code": req.room_code,
        "participant_name": req.participant_name,
        "team_code": req.team_name,
        "team_name": IPL_TEAMS[req.team_name],
        "claimed_teams": claimed,
    }


# ----------------------------------------------------------
# 4.  GET /auction/state?room_code=XXXX
# ----------------------------------------------------------
@app.get("/auction/state")
async def auction_state(room_code: str = Query(..., description="Room code, e.g. 3ZZ5EE")):
    """
    Returns the full live state for a room:
    participants, budgets, squads, active bids, deadline, phase, etc.
    """
    data = _firebase_get()
    rooms = data.get("rooms", {})
    room = rooms.get(room_code)
    if not room:
        raise HTTPException(status_code=404, detail=f"Room '{room_code}' not found")

    # Build a clean response
    participants_summary = []
    for p in room.get("participants", []):
        participants_summary.append({
            "name": p.get("name"),
            "budget": p.get("budget", 0),
            "squad_size": len(p.get("squad", [])),
            "eliminated": p.get("eliminated", False),
            "claim_code": room.get("claim_codes", {}).get(p.get("name")),
            "squad": [
                {
                    "name": pl.get("name"),
                    "role": pl.get("role", "Unknown"),
                    "team": pl.get("team", "Unknown"),
                    "price": pl.get("price", pl.get("buy_price", 0)),
                }
                for pl in p.get("squad", [])
            ],
        })

    return {
        "room_code": room_code,
        "admin": room.get("admin"),
        "tournament_type": room.get("tournament_type", "t20_wc"),
        "created_at": room.get("created_at"),
        "game_phase": room.get("game_phase", "Unknown"),
        "tournament_phase": room.get("tournament_phase", "super8"),
        "current_gameweek": room.get("current_gameweek", 1),
        "bidding_deadline": room.get("bidding_deadline"),
        "squads_locked": room.get("squads_locked", False),
        "active_bids": room.get("active_bids", []),
        "participants": participants_summary,
        "claimed_teams": room.get("claimed_teams", {}),
        "ipl_teams": room.get("ipl_teams", []),
    }


# ----------------------------------------------------------
# 5.  POST /auction/start
# ----------------------------------------------------------
@app.post("/auction/start")
async def auction_start(req: AuctionStartRequest):
    """
    Opens the bidding window for a room by setting the game phase
    to 'Bidding' and applying a deadline.  Only the room admin may
    call this endpoint.
    """
    data = _firebase_get()
    rooms = data.get("rooms", {})
    room = rooms.get(req.room_code)
    if not room:
        raise HTTPException(status_code=404, detail=f"Room '{req.room_code}' not found")

    # Admin-only guard
    if room.get("admin") != req.admin_name:
        raise HTTPException(
            status_code=403,
            detail=f"Only the room admin ('{room.get('admin')}') can start the auction",
        )

    now = _get_ist_now()
    deadline = now + timedelta(hours=req.deadline_hours)

    room["game_phase"] = "Bidding"
    room["bidding_deadline"] = deadline.isoformat()
    room["squads_locked"] = False

    # Write back
    _firebase_put(data)

    return {
        "message": "Auction started",
        "room_code": req.room_code,
        "deadline": deadline.isoformat(),
    }


# ----------------------------------------------------------
# 6.  POST /auction/bid
# ----------------------------------------------------------
@app.post("/auction/bid")
async def auction_bid(req: BidRequest):
    """
    Places or raises a bid with deadline-phase enforcement:
    - min bid 5M, increments of 5M once >= 50M
    - 1 hour before deadline: no NEW player initiations (only outbid existing)
    - 30 min before deadline: only 5M increments allowed
    - 30 min AFTER deadline: no trading at all
    - Rejects bids on players already owned by ANY participant
    """
    if req.amount < 5:
        raise HTTPException(status_code=400, detail="Minimum bid is 5M")

    # Validate increment rules (always: bids >= 50 must be in increments of 5)
    if req.amount >= 50 and req.amount % 5 != 0:
        raise HTTPException(status_code=400, detail="Bids of 50 or above must be in increments of 5")

    data = _firebase_get()
    rooms = data.get("rooms", {})
    room = rooms.get(req.room_code)
    if not room:
        raise HTTPException(status_code=404, detail=f"Room '{req.room_code}' not found")

    # --- Deadline phase enforcement ---
    deadline_str = room.get("bidding_deadline")
    now = _get_ist_now()
    is_new_player = True  # will be updated below
    if deadline_str:
        deadline = datetime.fromisoformat(deadline_str)
        dl_naive = deadline.replace(tzinfo=None)
        now_naive = now.replace(tzinfo=None)
        diff = (dl_naive - now_naive).total_seconds()

        # 30 min AFTER deadline → no trading at all
        if diff < -1800:
            raise HTTPException(status_code=400, detail="Trading window closed (30 min past deadline)")

        # Between deadline and 30 min after → no trading
        if diff < 0:
            raise HTTPException(status_code=400, detail="Bidding deadline has passed. No new bids allowed.")

        # 30 min before deadline → only 5M increments
        if diff <= 1800:
            if req.amount % 5 != 0:
                raise HTTPException(status_code=400, detail="Within 30 min of deadline: only increments of 5M allowed")

        # 1 hour before deadline → no new player initiations
        active_bids = room.get("active_bids", [])
        existing_bid = next((b for b in active_bids if b["player"] == req.player_name), None)
        is_new_player = existing_bid is None
        if diff <= 3600 and is_new_player:
            raise HTTPException(status_code=400, detail="Within 1 hour of deadline: cannot initiate bids on new players")

    # --- Reject bids on already‐owned players ---
    for p in room.get("participants", []):
        for sq_pl in p.get("squad", []):
            if sq_pl.get("name") == req.player_name:
                raise HTTPException(
                    status_code=400,
                    detail=f"Player '{req.player_name}' is already in {p['name']}'s squad",
                )

    # Find participant
    participant = None
    for p in room.get("participants", []):
        if p.get("name") == req.participant_name:
            participant = p
            break
    if not participant:
        raise HTTPException(status_code=404, detail=f"Participant '{req.participant_name}' not found")
    if participant.get("eliminated", False):
        raise HTTPException(status_code=403, detail="Eliminated participants cannot bid")

    # Budget check (account for other active bids)
    active_bids = room.get("active_bids", [])
    committed = sum(
        b["amount"] for b in active_bids
        if b["bidder"] == req.participant_name and b["player"] != req.player_name
    )
    available = participant.get("budget", 0) - committed
    if req.amount > available:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient budget. Total: {participant.get('budget', 0)}M, "
                   f"committed: {committed}M, available: {available}M",
        )

    # Check existing bid on this player
    existing = next((b for b in active_bids if b["player"] == req.player_name), None)
    if existing:
        curr = existing["amount"]
        if req.amount <= curr:
            raise HTTPException(
                status_code=400,
                detail=f"Must outbid current bid of {curr}M",
            )
        active_bids.remove(existing)

    # Place the bid
    expiry = (now + timedelta(hours=24)).isoformat()
    active_bids.append({
        "player": req.player_name,
        "amount": req.amount,
        "bidder": req.participant_name,
        "expires": expiry,
    })
    room["active_bids"] = active_bids

    _firebase_put(data)

    return {
        "message": f"Bid placed on {req.player_name} for {req.amount}M",
        "bidder": req.participant_name,
        "expires": expiry,
    }


# ----------------------------------------------------------
# 7.  GET /auction/results?room_code=XXXX
# ----------------------------------------------------------
@app.get("/auction/results")
async def auction_results(room_code: str = Query(..., description="Room code")):
    """
    Returns standings / leaderboard for the room.
    Uses the same Best-11 logic as streamlit_app.py by importing
    CricketScoreCalculator for individual player scoring.
    """
    data = _firebase_get()
    rooms = data.get("rooms", {})
    room = rooms.get(room_code)
    if not room:
        raise HTTPException(status_code=404, detail=f"Room '{room_code}' not found")

    gameweek_scores = room.get("gameweek_scores", {})
    if not gameweek_scores:
        return {
            "room_code": room_code,
            "message": "No gameweek scores processed yet",
            "standings": [],
        }

    # Calculate cumulative standings (mirrors streamlit_app.py logic)
    active_participants = [
        p for p in room.get("participants", [])
        if not p.get("eliminated", False)
    ]

    p_totals = {p["name"]: 0.0 for p in active_participants}
    p_gw_breakdown = {p["name"]: {} for p in active_participants}

    for gw, scores in gameweek_scores.items():
        locked_squads = room.get("gameweek_squads", {}).get(str(gw), {})

        # Apply hattrick bonuses
        scores_with_bonus = dict(scores)
        hattrick_bonuses = room.get("hattrick_bonuses", {}).get(gw, {})
        for player, bonus in hattrick_bonuses.items():
            scores_with_bonus[player] = scores_with_bonus.get(player, 0) + bonus

        for participant in active_participants:
            p_name = participant["name"]

            # Resolve squad for this GW
            squad_data = locked_squads.get(p_name)
            if squad_data:
                if isinstance(squad_data, list):
                    squad = squad_data
                    ir_player = None
                else:
                    squad = squad_data.get("squad", [])
                    ir_player = squad_data.get("injury_reserve")
            else:
                squad = participant.get("squad", [])
                ir_player = participant.get("injury_reserve")

            # Get scores for squad (exclude IR)
            squad_scores = []
            for pl in squad:
                name = pl["name"] if isinstance(pl, dict) else pl
                if name == ir_player:
                    continue
                squad_scores.append({
                    "name": name,
                    "score": scores_with_bonus.get(name, 0),
                })

            # Best 11 (simple: top 11 by score)
            squad_scores.sort(key=lambda x: -x["score"])
            best_11 = squad_scores[:11]
            gw_points = sum(s["score"] for s in best_11)

            p_totals[p_name] += gw_points
            p_gw_breakdown[p_name][gw] = gw_points

    # Build sorted standings
    standings = sorted(
        [
            {
                "rank": 0,
                "participant": name,
                "total_points": pts,
                "gameweek_breakdown": p_gw_breakdown[name],
            }
            for name, pts in p_totals.items()
        ],
        key=lambda x: -x["total_points"],
    )
    for i, entry in enumerate(standings):
        entry["rank"] = i + 1

    return {
        "room_code": room_code,
        "gameweeks_processed": list(gameweek_scores.keys()),
        "standings": standings,
    }


# ==========================================================
# PARALLEL IDENTITY LAYER (mobile app only)
#
# Adds user accounts alongside the existing participant
# format WITHOUT modifying rooms/{code}/participants (except
# temporary claim_token / claim_token_expires fields).
#
# Firebase nodes:
#   auction_data/users/{uid}                    → user profile
#   auction_data/room_user_map/{code}/{name}    → uid
#
# Linking flow:
#   1. Website admin calls POST /user/generate-claim-token
#      → writes claim_token + claim_token_expires into the
#        participant object and returns the token.
#   2. Mobile user calls POST /user/link-participant
#      with the token → validates, links uid, invalidates token.
#   3. GET /user/rooms?uid=XXX returns all rooms linked to uid.
#
# NOTE on Firebase Auth:
#   Enabling Email/Password sign-in in Firebase Console will
#   NOT delete or lock the existing Realtime Database. It is
#   safe to enable and is recommended for production.
#   This code does not enable it; do that in the Console.
# ==========================================================

# ----------------------------------------------------------
# 8.  POST /user/generate-claim-token  (admin only)
# ----------------------------------------------------------
@app.post("/user/generate-claim-token", response_model=ClaimTokenResponse)
async def generate_claim_token(req: GenerateClaimTokenRequest):
    """
    Generates a single-use claim token so a mobile user can link
    their Firebase Auth uid to an existing participant.

    Only the room admin may call this endpoint.
    The token is valid for 1 hour.

    Example:
        curl -X POST http://localhost:8000/user/generate-claim-token \\
          -H 'Content-Type: application/json' \\
          -d '{"room_code": "ABC123", "participant_name": "Bob", "admin_name": "Alice"}'

        → {"claim_token": "aB3xZ9qK2m", "expires": "2026-03-04T17:05:00+05:30"}
    """
    data = _firebase_get()
    rooms = data.get("rooms", {})
    room = rooms.get(req.room_code)
    if not room:
        raise HTTPException(status_code=404, detail=f"Room '{req.room_code}' not found")

    # Admin-only guard
    if room.get("admin") != req.admin_name:
        raise HTTPException(
            status_code=403,
            detail=f"Only the room admin ('{room.get('admin')}') can generate claim tokens",
        )

    # Find participant
    participants = room.get("participants", [])
    target_idx = None
    for i, p in enumerate(participants):
        if p.get("name") == req.participant_name:
            target_idx = i
            break
    if target_idx is None:
        raise HTTPException(
            status_code=404,
            detail=f"Participant '{req.participant_name}' not found in room '{req.room_code}'",
        )

    # Generate token
    token = _generate_claim_token()
    now = _get_ist_now()
    expires = now + timedelta(hours=1)

    # Patch only the participant's token fields (minimal write)
    participants[target_idx]["claim_token"] = token
    participants[target_idx]["claim_token_expires"] = expires.isoformat()
    room["participants"] = participants
    _firebase_put(data)

    return {
        "claim_token": token,
        "expires": expires.isoformat(),
        "participant_name": req.participant_name,
        "room_code": req.room_code,
    }


# ----------------------------------------------------------
# 9.  POST /user/link-participant  (claim-token validated)
# ----------------------------------------------------------
@app.post("/user/link-participant", response_model=LinkParticipantResponse)
async def link_participant(req: LinkParticipantRequest):
    """
    Links a Firebase Auth uid to an existing participant using
    a single-use claim token generated by the admin.

    Security:
    - Token must match the participant's claim_token
    - Token must not be expired (claim_token_expires in future)
    - Participant must not already be linked to a different uid
    - Token is invalidated (removed) after use

    Example:
        curl -X POST http://localhost:8000/user/link-participant \\
          -H 'Content-Type: application/json' \\
          -d '{"room_code": "ABC123", "participant_name": "Bob", "claim_token": "aB3xZ9qK2m", "uid": "firebase_uid_456"}'

        → {"linked": true, "room_code": "ABC123", "participant_name": "Bob", "uid": "firebase_uid_456"}

    Note on concurrency: Firebase REST API does not provide atomic
    compare-and-set. In the unlikely event of a race (two clients
    linking simultaneously), the last writer wins. The room_user_map
    check-and-set is best-effort; for production scale, consider
    Firebase Cloud Functions with transactions.
    """
    data = _firebase_get()
    rooms = data.get("rooms", {})
    room = rooms.get(req.room_code)
    if not room:
        raise HTTPException(status_code=404, detail=f"Room '{req.room_code}' not found")

    # Find participant
    participants = room.get("participants", [])
    target_idx = None
    for i, p in enumerate(participants):
        if p.get("name") == req.participant_name:
            target_idx = i
            break
    if target_idx is None:
        raise HTTPException(
            status_code=404,
            detail=f"Participant '{req.participant_name}' not found in room '{req.room_code}'",
        )

    participant = participants[target_idx]

    # Validate claim token
    stored_token = participant.get("claim_token")
    if not stored_token or stored_token != req.claim_token:
        raise HTTPException(
            status_code=400,
            detail="Invalid claim token. Request a new token from the room admin.",
        )

    # Validate expiry
    expires_str = participant.get("claim_token_expires", "")
    now = _get_ist_now()
    try:
        expires_dt = datetime.fromisoformat(expires_str)
        if now.replace(tzinfo=None) >= expires_dt.replace(tzinfo=None):
            raise HTTPException(
                status_code=400,
                detail="Claim token has expired. Request a new token from the room admin.",
            )
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=400,
            detail="Claim token metadata is corrupted. Request a new token.",
        )

    # Check if already linked to a different uid
    room_user_map = data.get("room_user_map", {})
    room_map = room_user_map.get(req.room_code, {})
    existing_uid = room_map.get(req.participant_name)
    if existing_uid and existing_uid != req.uid:
        raise HTTPException(
            status_code=409,
            detail="This participant is already claimed by another account. Contact the room admin.",
        )

    # --- Link: update room_user_map ---
    if req.room_code not in room_user_map:
        room_user_map[req.room_code] = {}
    room_user_map[req.room_code][req.participant_name] = req.uid
    data["room_user_map"] = room_user_map

    # --- Link: update users/{uid} ---
    users = data.setdefault("users", {})
    profile = users.setdefault(req.uid, {})
    profile["display_name"] = req.participant_name
    user_rooms = profile.setdefault("rooms", {})
    user_rooms[req.room_code] = req.participant_name

    # --- Invalidate token (remove from participant) ---
    participant.pop("claim_token", None)
    participant.pop("claim_token_expires", None)
    participants[target_idx] = participant
    room["participants"] = participants

    _firebase_put(data)

    return {
        "linked": True,
        "room_code": req.room_code,
        "participant_name": req.participant_name,
        "uid": req.uid,
    }


# ----------------------------------------------------------
# 10.  GET /user/rooms?uid=XXX
# ----------------------------------------------------------
@app.get("/user/rooms", response_model=UserRoomsResponse)
async def user_rooms(uid: str = Query(..., description="Firebase Auth user ID")):
    """
    Returns all rooms the authenticated user is linked to.
    Reads users/{uid}/rooms mapping and enriches with room metadata.

    Example:
        curl 'http://localhost:8000/user/rooms?uid=firebase_uid_456'

        → {"uid": "firebase_uid_456", "display_name": "Bob", "rooms": [
              {"room_code": "ABC123", "participant_name": "Bob", ...}
           ]}
    """
    data = _firebase_get()
    user_profile = data.get("users", {}).get(uid)
    if not user_profile:
        return {"uid": uid, "display_name": "", "rooms": []}

    user_room_map = user_profile.get("rooms", {})
    rooms = data.get("rooms", {})

    room_list = []
    for code, participant_name in user_room_map.items():
        room = rooms.get(code)
        if not room:
            continue  # room was deleted
        is_admin = room.get("admin") == participant_name
        participant_count = len(room.get("participants", []))
        room_list.append({
            "room_code": code,
            "participant_name": participant_name,
            "tournament_type": room.get("tournament_type", "t20_wc"),
            "game_phase": room.get("game_phase", "Unknown"),
            "admin": room.get("admin", ""),
            "role": "admin" if is_admin else "participant",
            "is_admin": is_admin,
            "participant_count": participant_count,
            "created_at": room.get("created_at"),
        })

    # Sort newest first
    room_list.sort(key=lambda r: r.get("created_at", ""), reverse=True)

    return {
        "uid": uid,
        "display_name": user_profile.get("display_name", ""),
        "rooms": room_list,
    }


# ----------------------------------------------------------
# 11.  GET /players  (global player database)
# ----------------------------------------------------------
@app.get("/players", response_model=PlayersResponse)
async def get_players(
    role: Optional[str] = Query(None, description="Filter by role: Batsman, Bowler, All-Rounder, WK"),
    team: Optional[str] = Query(None, description="Filter by team: India, England, etc."),
):
    """
    Returns the global player database with optional filters.

    Example:
        curl 'http://localhost:8000/players?role=Batsman&team=India'
    """
    url = f"{FIREBASE_URL}/auction_data/players.json"
    try:
        resp = http_requests.get(url, timeout=10)
        resp.raise_for_status()
        raw = resp.json() or {}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Firebase read failed: {e}")

    players = []
    for _key, p in raw.items():
        if not isinstance(p, dict):
            continue
        if role and p.get("role", "").lower() != role.lower():
            continue
        if team and p.get("team", "").lower() != team.lower():
            continue
        players.append({
            "name": p.get("name", _key),
            "role": p.get("role", "Unknown"),
            "team": p.get("team", "Unknown"),
            "base_price": p.get("base_price", 10),
        })

    players.sort(key=lambda x: x["name"])
    return {"players": players, "total": len(players)}


# ----------------------------------------------------------
# 12.  POST /seed-players  (one-time player DB seeder)
# ----------------------------------------------------------
@app.post("/seed-players")
async def seed_players():
    """
    Seeds the global player database into Firebase.
    Call once to populate auction_data/players/.
    Idempotent — overwrites existing data.
    """
    player_db = {
        "virat_kohli":      {"name": "Virat Kohli",      "role": "Batsman",      "team": "India",         "base_price": 20},
        "rohit_sharma":     {"name": "Rohit Sharma",     "role": "Batsman",      "team": "India",         "base_price": 18},
        "suryakumar_yadav": {"name": "Suryakumar Yadav", "role": "Batsman",      "team": "India",         "base_price": 16},
        "shubman_gill":     {"name": "Shubman Gill",     "role": "Batsman",      "team": "India",         "base_price": 14},
        "hardik_pandya":    {"name": "Hardik Pandya",    "role": "All-Rounder",  "team": "India",         "base_price": 16},
        "ravindra_jadeja":  {"name": "Ravindra Jadeja",  "role": "All-Rounder",  "team": "India",         "base_price": 14},
        "jasprit_bumrah":   {"name": "Jasprit Bumrah",   "role": "Bowler",       "team": "India",         "base_price": 18},
        "kuldeep_yadav":    {"name": "Kuldeep Yadav",    "role": "Bowler",       "team": "India",         "base_price": 12},
        "rishabh_pant":     {"name": "Rishabh Pant",     "role": "WK",           "team": "India",         "base_price": 16},
        "jos_buttler":      {"name": "Jos Buttler",      "role": "WK",           "team": "England",       "base_price": 18},
        "ben_stokes":       {"name": "Ben Stokes",       "role": "All-Rounder",  "team": "England",       "base_price": 16},
        "jofra_archer":     {"name": "Jofra Archer",     "role": "Bowler",       "team": "England",       "base_price": 14},
        "harry_brook":      {"name": "Harry Brook",      "role": "Batsman",      "team": "England",       "base_price": 14},
        "phil_salt":        {"name": "Phil Salt",        "role": "WK",           "team": "England",       "base_price": 12},
        "pat_cummins":      {"name": "Pat Cummins",      "role": "Bowler",       "team": "Australia",     "base_price": 16},
        "travis_head":      {"name": "Travis Head",      "role": "Batsman",      "team": "Australia",     "base_price": 14},
        "mitchell_starc":   {"name": "Mitchell Starc",   "role": "Bowler",       "team": "Australia",     "base_price": 16},
        "glenn_maxwell":    {"name": "Glenn Maxwell",    "role": "All-Rounder",  "team": "Australia",     "base_price": 14},
        "david_warner":     {"name": "David Warner",     "role": "Batsman",      "team": "Australia",     "base_price": 14},
        "rashid_khan":      {"name": "Rashid Khan",      "role": "Bowler",       "team": "Afghanistan",   "base_price": 16},
        "babar_azam":       {"name": "Babar Azam",       "role": "Batsman",      "team": "Pakistan",      "base_price": 16},
        "shaheen_afridi":   {"name": "Shaheen Afridi",   "role": "Bowler",       "team": "Pakistan",      "base_price": 14},
        "trent_boult":      {"name": "Trent Boult",      "role": "Bowler",       "team": "New Zealand",   "base_price": 14},
        "kane_williamson":  {"name": "Kane Williamson",  "role": "Batsman",      "team": "New Zealand",   "base_price": 14},
        "quinton_de_kock":  {"name": "Quinton de Kock",  "role": "WK",           "team": "South Africa",  "base_price": 14},
        "kagiso_rabada":    {"name": "Kagiso Rabada",    "role": "Bowler",       "team": "South Africa",  "base_price": 14},
        "aiden_markram":    {"name": "Aiden Markram",    "role": "All-Rounder",  "team": "South Africa",  "base_price": 12},
        "nicholas_pooran":  {"name": "Nicholas Pooran",  "role": "WK",           "team": "West Indies",   "base_price": 12},
        "andre_russell":    {"name": "Andre Russell",    "role": "All-Rounder",  "team": "West Indies",   "base_price": 14},
        "wanindu_hasaranga": {"name": "Wanindu Hasaranga", "role": "All-Rounder", "team": "Sri Lanka",     "base_price": 12},
        "sam_curran":       {"name": "Sam Curran",       "role": "All-Rounder",  "team": "England",       "base_price": 14},
    }

    url = f"{FIREBASE_URL}/auction_data/players.json"
    try:
        resp = http_requests.put(
            url, json=player_db,
            headers={"Content-Type": "application/json"}, timeout=15,
        )
        resp.raise_for_status()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Firebase write failed: {e}")

    return {"message": f"Seeded {len(player_db)} players", "total": len(player_db)}


# ----------------------------------------------------------
# Bonus: POST /calculate  (existing scoring calculator)
# ----------------------------------------------------------
@app.post("/calculate")
async def calculate_points(url: str = Query(..., description="Cricbuzz scorecard URL")):
    """
    Exposes the existing CricbuzzScraper + CricketScoreCalculator
    pipeline as a REST endpoint.
    """
    try:
        players_data = scraper.fetch_match_data(url)
        if not players_data:
            raise HTTPException(status_code=404, detail="No player data found for URL")

        results = []
        for p in players_data:
            score = calculator.calculate_score(p)
            results.append({
                "name": p["name"],
                "role": p.get("role", "Unknown"),
                "points": round(score, 1),
                "runs": p.get("runs", 0),
                "wickets": p.get("wickets", 0),
                "catches": p.get("catches", 0),
            })
        results.sort(key=lambda x: -x["points"])
        return {"players": results, "total_players": len(results)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ----------------------------------------------------------
# 13.  POST /auction/trade/propose
# ----------------------------------------------------------
@app.post("/auction/trade/propose")
async def trade_propose(req: TradeProposalRequest):
    """Create a trade proposal. Types: Transfer (Sell/Buy), Exchange, Loan Out/In."""
    import uuid as uuid_lib
    data = _firebase_get()
    room = data.get("rooms", {}).get(req.room_code)
    if not room:
        raise HTTPException(status_code=404, detail=f"Room '{req.room_code}' not found")

    if room.get("squads_locked"):
        raise HTTPException(status_code=403, detail="Market is locked. Cannot trade.")

    # Validate participants exist
    participants = room.get("participants", [])
    sender = next((p for p in participants if p["name"] == req.from_participant), None)
    receiver = next((p for p in participants if p["name"] == req.to_participant), None)
    if not sender:
        raise HTTPException(status_code=404, detail=f"Sender '{req.from_participant}' not found")
    if not receiver:
        raise HTTPException(status_code=404, detail=f"Receiver '{req.to_participant}' not found")

    # Build trade object
    trade = {
        "id": str(uuid_lib.uuid4()),
        "from": req.from_participant,
        "to": req.to_participant,
        "type": req.trade_type,
        "price": req.price,
        "created_at": _get_ist_now().isoformat(),
        "status": "pending",
    }
    if req.trade_type == "Exchange":
        trade["give_player"] = req.give_player
        trade["get_player"] = req.get_player
    else:
        trade["player"] = req.player

    # Duplicate check
    pending = room.get("pending_trades", [])
    for t in pending:
        if (t["from"] == req.from_participant and t["to"] == req.to_participant
                and t["type"] == req.trade_type and t.get("player") == trade.get("player")
                and t.get("give_player") == trade.get("give_player")
                and t.get("price") == req.price and t.get("status") != "pending_admin"):
            raise HTTPException(status_code=409, detail="Duplicate proposal already exists")

    pending.append(trade)
    room["pending_trades"] = pending
    _firebase_put(data)
    return {"message": "Proposal sent", "trade_id": trade["id"]}


# ----------------------------------------------------------
# 14.  POST /auction/trade/respond
# ----------------------------------------------------------
@app.post("/auction/trade/respond")
async def trade_respond(req: TradeRespondRequest):
    """Counterparty accepts or rejects a trade proposal."""
    data = _firebase_get()
    room = data.get("rooms", {}).get(req.room_code)
    if not room:
        raise HTTPException(status_code=404, detail=f"Room '{req.room_code}' not found")

    pending = room.get("pending_trades", [])
    trade = next((t for t in pending if t["id"] == req.trade_id), None)
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    if trade["to"] != req.participant_name:
        raise HTTPException(status_code=403, detail="Only the counterparty can respond")

    if req.action == "reject":
        room["pending_trades"] = [t for t in pending if t["id"] != req.trade_id]
        timestamp = _get_ist_now().strftime("%d-%b %H:%M")
        room.setdefault("trade_log", []).append({
            "time": timestamp,
            "msg": f"❌ Rejected: **{trade['to']}** rejected proposal from **{trade['from']}**"
        })
        _firebase_put(data)
        return {"message": "Trade rejected", "trade_id": req.trade_id}
    else:
        # Accept → move to pending_admin for admin approval
        trade["status"] = "pending_admin"
        trade["agreed_at"] = _get_ist_now().isoformat()
        _firebase_put(data)
        return {"message": "Trade accepted, waiting for admin approval", "trade_id": req.trade_id}


# ----------------------------------------------------------
# 15.  POST /auction/trade/admin-action
# ----------------------------------------------------------
@app.post("/auction/trade/admin-action")
async def trade_admin_action(req: TradeAdminRequest):
    """Admin approves or rejects a pending_admin trade. On approve, executes the trade."""
    import math
    data = _firebase_get()
    room = data.get("rooms", {}).get(req.room_code)
    if not room:
        raise HTTPException(status_code=404, detail=f"Room '{req.room_code}' not found")
    if room.get("admin") != req.admin_name:
        raise HTTPException(status_code=403, detail="Only admin can approve/reject trades")

    pending = room.get("pending_trades", [])
    trade = next((t for t in pending if t["id"] == req.trade_id and t.get("status") == "pending_admin"), None)
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found or not pending admin")

    participants = room.get("participants", [])
    sender = next((p for p in participants if p["name"] == trade["from"]), None)
    receiver = next((p for p in participants if p["name"] == trade["to"]), None)
    timestamp = _get_ist_now().strftime("%d-%b %H:%M")

    if req.action == "reject":
        room["pending_trades"] = [t for t in pending if t["id"] != req.trade_id]
        room.setdefault("trade_log", []).append({
            "time": timestamp,
            "msg": f"❌ Admin Rejected: **{trade['type']}** between **{trade['from']}** and **{trade['to']}**"
        })
        _firebase_put(data)
        return {"message": "Trade rejected by admin"}

    # APPROVE: re-validate and execute
    if not sender or not receiver:
        raise HTTPException(status_code=400, detail="Sender or receiver no longer exists")

    t_type = trade["type"]
    t_price = float(trade.get("price", 0))
    success = False
    fail_reason = "Unknown error"
    log_msg = ""

    if t_type == "Transfer (Sell)":
        p_obj = next((p for p in sender["squad"] if p["name"] == trade["player"]), None)
        if not p_obj:
            fail_reason = f"Seller no longer owns {trade['player']}"
        elif float(receiver.get("budget", 0)) < t_price:
            fail_reason = "Buyer insufficient funds"
        else:
            sender["squad"].remove(p_obj)
            p_obj["buy_price"] = t_price
            receiver["squad"].append(p_obj)
            sender["budget"] = float(sender.get("budget", 0)) + t_price
            receiver["budget"] = float(receiver.get("budget", 0)) - t_price
            success = True
            log_msg = f"🔄 Transfer: **{trade['to']}** bought **{trade['player']}** from **{trade['from']}** for **{t_price}M**"

    elif t_type == "Transfer (Buy)":
        p_obj = next((p for p in receiver["squad"] if p["name"] == trade["player"]), None)
        if not p_obj:
            fail_reason = f"Seller no longer owns {trade['player']}"
        elif float(sender.get("budget", 0)) < t_price:
            fail_reason = "Buyer insufficient funds"
        else:
            receiver["squad"].remove(p_obj)
            p_obj["buy_price"] = t_price
            sender["squad"].append(p_obj)
            receiver["budget"] = float(receiver.get("budget", 0)) + t_price
            sender["budget"] = float(sender.get("budget", 0)) - t_price
            success = True
            log_msg = f"🔄 Transfer: **{trade['from']}** bought **{trade['player']}** from **{trade['to']}** for **{t_price}M**"

    elif t_type == "Exchange":
        give_pl = trade.get("give_player")
        get_pl = trade.get("get_player")
        p_give = next((p for p in sender["squad"] if p["name"] == give_pl), None)
        p_get = next((p for p in receiver["squad"] if p["name"] == get_pl), None)
        if not p_give:
            fail_reason = f"{sender['name']} no longer has {give_pl}"
        elif not p_get:
            fail_reason = f"{receiver['name']} no longer has {get_pl}"
        elif t_price > 0 and float(sender.get("budget", 0)) < t_price:
            fail_reason = f"{sender['name']} can't afford {t_price}M"
        elif t_price < 0 and float(receiver.get("budget", 0)) < abs(t_price):
            fail_reason = f"{receiver['name']} can't afford {abs(t_price)}M"
        else:
            sender["squad"].remove(p_give)
            receiver["squad"].remove(p_get)
            sender["squad"].append(p_get)
            receiver["squad"].append(p_give)
            sender["budget"] = float(sender.get("budget", 0)) - t_price
            receiver["budget"] = float(receiver.get("budget", 0)) + t_price
            success = True
            cash_txt = f"(+{t_price}M)" if t_price > 0 else f"(-{abs(t_price)}M)" if t_price < 0 else "(Flat)"
            log_msg = f"💱 Exchange: **{trade['from']}** ({give_pl}) ↔ **{trade['to']}** ({get_pl}) {cash_txt}"

    elif t_type in ("Loan Out", "Loan In"):
        curr_gw = room.get("current_gameweek", 1)
        return_gw = curr_gw + 1
        if t_type == "Loan Out":
            pl_name = trade["player"]
            p_obj = next((p for p in sender["squad"] if p["name"] == pl_name), None)
            if not p_obj:
                fail_reason = f"{sender['name']} doesn't have {pl_name}"
            elif float(receiver.get("budget", 0)) < t_price:
                fail_reason = "Insufficient funds"
            else:
                sender["squad"].remove(p_obj)
                p_obj["loan_origin"] = sender["name"]
                p_obj["loan_expiry_gw"] = return_gw
                receiver["squad"].append(p_obj)
                sender["budget"] = float(sender.get("budget", 0)) + t_price
                receiver["budget"] = float(receiver.get("budget", 0)) - t_price
                success = True
                log_msg = f"⏳ Loan: **{trade['from']}** loaned **{pl_name}** to **{trade['to']}** for **{t_price}M**"
        else:  # Loan In
            pl_name = trade["player"]
            p_obj = next((p for p in receiver["squad"] if p["name"] == pl_name), None)
            if not p_obj:
                fail_reason = f"{receiver['name']} doesn't have {pl_name}"
            elif float(sender.get("budget", 0)) < t_price:
                fail_reason = "Insufficient funds"
            else:
                receiver["squad"].remove(p_obj)
                p_obj["loan_origin"] = receiver["name"]
                p_obj["loan_expiry_gw"] = return_gw
                sender["squad"].append(p_obj)
                receiver["budget"] = float(receiver.get("budget", 0)) + t_price
                sender["budget"] = float(sender.get("budget", 0)) - t_price
                success = True
                log_msg = f"⏳ Loan: **{trade['to']}** loaned **{pl_name}** to **{trade['from']}** for **{t_price}M**"

    if success:
        room["pending_trades"] = [t for t in pending if t["id"] != req.trade_id]
        if log_msg:
            room.setdefault("trade_log", []).append({"time": timestamp, "msg": log_msg})
        _firebase_put(data)
        return {"message": "Trade approved and executed", "trade_id": req.trade_id}
    else:
        raise HTTPException(status_code=400, detail=f"Trade failed: {fail_reason}")


# ----------------------------------------------------------
# 16.  POST /auction/trade/force
# ----------------------------------------------------------
@app.post("/auction/trade/force")
async def trade_force(req: TradeForceRequest):
    """Admin force-executes a trade (no proposal needed)."""
    data = _firebase_get()
    room = data.get("rooms", {}).get(req.room_code)
    if not room:
        raise HTTPException(status_code=404, detail=f"Room not found")
    if room.get("admin") != req.admin_name:
        raise HTTPException(status_code=403, detail="Admin only")

    participants = room.get("participants", [])
    sender = next((p for p in participants if p["name"] == req.sender_name), None)
    receiver = next((p for p in participants if p["name"] == req.receiver_name), None)
    if not sender or not receiver:
        raise HTTPException(status_code=404, detail="Participant not found")

    p_obj = next((p for p in sender["squad"] if p["name"] == req.player_name), None)
    if not p_obj:
        raise HTTPException(status_code=400, detail=f"Player not in sender's squad")

    sender["squad"].remove(p_obj)
    receiver["squad"].append(p_obj)
    sender["budget"] = float(sender.get("budget", 0)) + req.price
    receiver["budget"] = float(receiver.get("budget", 0)) - req.price

    timestamp = _get_ist_now().strftime("%d-%b %H:%M")
    room.setdefault("trade_log", []).append({
        "time": timestamp,
        "msg": f"👑 Admin Force: **{req.player_name}** moved from **{req.sender_name}** to **{req.receiver_name}** for **{req.price}M**"
    })
    _firebase_put(data)
    return {"message": f"Force trade executed: {req.player_name}"}


# ----------------------------------------------------------
# 17.  POST /auction/boost
# ----------------------------------------------------------
@app.post("/auction/boost")
async def grant_boost(req: BoostRequest):
    """Admin grants one-time 100M budget boost to all participants."""
    data = _firebase_get()
    room = data.get("rooms", {}).get(req.room_code)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    if room.get("admin") != req.admin_name:
        raise HTTPException(status_code=403, detail="Admin only")
    if room.get("gw2_boost_given"):
        raise HTTPException(status_code=409, detail="100M boost already granted")

    for p in room.get("participants", []):
        p["budget"] = float(p.get("budget", 0)) + 100
    room["gw2_boost_given"] = True
    _firebase_put(data)
    return {"message": "100M boost granted to all participants"}


# ----------------------------------------------------------
# 18.  POST /auction/lock-squads
# ----------------------------------------------------------
@app.post("/auction/lock-squads")
async def lock_squads(req: LockSquadsRequest):
    """
    Admin locks squads for current GW with full enforcement:
    - Max 19 players: auto-release cheapest if > 19
    - Min 12 players: warn but don't block
    - IR rules:
      * < 19 players → IR ignored (no cost)
      * 19 players + IR set → 2M deducted from budget
      * 19+ players + no IR → most expensive player auto-assigned as IR
    - Creates snapshot for scoring
    """
    import math
    data = _firebase_get()
    room = data.get("rooms", {}).get(req.room_code)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    if room.get("admin") != req.admin_name:
        raise HTTPException(status_code=403, detail="Admin only")

    curr_gw = room.get("current_gameweek", 1)
    gw_key = str(curr_gw)
    lock_log = []

    for p in room.get("participants", []):
        if p.get("eliminated", False):
            continue
        squad = p.get("squad", [])
        p_name = p["name"]

        # --- Enforce max 19: auto-release cheapest ---
        while len(squad) > 19:
            cheapest = min(squad, key=lambda x: float(x.get("buy_price", x.get("price", 0))))
            squad.remove(cheapest)
            lock_log.append(f"Auto-released {cheapest.get('name')} from {p_name} (over 19)")
        p["squad"] = squad

        # --- Injury Reserve rules ---
        ir_player = p.get("injury_reserve")

        if len(squad) < 19:
            # < 19 players: IR doesn't count (no cost, ignore it)
            p["injury_reserve_active"] = None
        elif len(squad) == 19:
            if ir_player:
                # 19 players + IR set → 2M deduction
                p["budget"] = float(p.get("budget", 0)) - 2
                p["injury_reserve_active"] = ir_player
                lock_log.append(f"{p_name}: IR ({ir_player}), -2M")
            else:
                # 19 players + no IR set → most expensive player becomes IR
                most_expensive = max(squad, key=lambda x: float(x.get("buy_price", x.get("price", 0))))
                p["injury_reserve"] = most_expensive.get("name")
                p["injury_reserve_active"] = most_expensive.get("name")
                p["budget"] = float(p.get("budget", 0)) - 2
                lock_log.append(f"{p_name}: Auto-IR ({most_expensive.get('name')}), -2M")

        # Warn if < 12
        if len(squad) < 12:
            lock_log.append(f"WARNING: {p_name} has only {len(squad)} players (min 12 recommended)")

    # Snapshot all squads
    gw_squads = room.get("gameweek_squads", {})
    snapshot = {}
    for p in room.get("participants", []):
        snapshot[p["name"]] = {
            "squad": list(p["squad"]),
            "injury_reserve": p.get("injury_reserve_active", p.get("injury_reserve")),
        }
    gw_squads[gw_key] = snapshot
    room["gameweek_squads"] = gw_squads
    room["squads_locked"] = True
    _firebase_put(data)
    return {"message": f"Squads locked for GW{curr_gw}", "gameweek": curr_gw, "log": lock_log}


# ----------------------------------------------------------
# 19.  POST /auction/advance-gameweek
# ----------------------------------------------------------
@app.post("/auction/advance-gameweek")
async def advance_gameweek(req: AdvanceGameweekRequest):
    """Admin advances to next GW. Requires squads_locked. Returns any loaned players."""
    data = _firebase_get()
    room = data.get("rooms", {}).get(req.room_code)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    if room.get("admin") != req.admin_name:
        raise HTTPException(status_code=403, detail="Admin only")
    if not room.get("squads_locked"):
        raise HTTPException(status_code=400, detail="Squads must be locked before advancing to the next gameweek")

    curr_gw = room.get("current_gameweek", 1)
    new_gw = curr_gw + 1

    # Return loaned players
    loan_returns = []
    for p in room.get("participants", []):
        returning = [pl for pl in p["squad"] if pl.get("loan_expiry_gw") == curr_gw]
        for pl in returning:
            origin_name = pl.get("loan_origin")
            origin = next((pp for pp in room.get("participants", []) if pp["name"] == origin_name), None)
            if origin:
                p["squad"].remove(pl)
                pl.pop("loan_origin", None)
                pl.pop("loan_expiry_gw", None)
                origin["squad"].append(pl)
                loan_returns.append(f"{pl['name']} returned to {origin_name}")

    # Clear IR active flags for fresh GW
    for p in room.get("participants", []):
        p.pop("injury_reserve_active", None)

    room["current_gameweek"] = new_gw
    room["squads_locked"] = False
    room["bidding_deadline"] = None  # Reset deadline for new GW
    _firebase_put(data)
    return {"message": f"Advanced to GW{new_gw}", "gameweek": new_gw, "loan_returns": loan_returns}


# ----------------------------------------------------------
# 20.  POST /auction/release-player
# ----------------------------------------------------------
@app.post("/auction/release-player")
async def release_player(req: ReleasePlayerRequest):
    """Release a player from squad with refund logic."""
    import math
    data = _firebase_get()
    room = data.get("rooms", {}).get(req.room_code)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    if room.get("squads_locked"):
        raise HTTPException(status_code=403, detail="Market is locked")

    participant = next((p for p in room.get("participants", []) if p["name"] == req.participant_name), None)
    if not participant:
        raise HTTPException(status_code=404, detail="Participant not found")

    player_obj = next((p for p in participant["squad"] if p["name"] == req.player_name), None)
    if not player_obj:
        raise HTTPException(status_code=404, detail="Player not in squad")
    if player_obj.get("loan_origin"):
        raise HTTPException(status_code=400, detail="Cannot release loaned player")

    # Release logic: check pre-deadline or paid/free
    curr_gw = room.get("current_gameweek", 1)
    has_season_started = len(room.get("gameweek_squads", {})) > 0
    now = _get_ist_now()
    deadline_str = room.get("bidding_deadline")
    global_deadline = datetime.fromisoformat(deadline_str) if deadline_str else None
    is_pre_deadline = (not has_season_started) and (global_deadline and now.replace(tzinfo=None) < global_deadline.replace(tzinfo=None))

    paid_releases = participant.get("paid_releases", {})
    if isinstance(paid_releases, list):
        used_paid = paid_releases[curr_gw] if curr_gw < len(paid_releases) and paid_releases[curr_gw] else False
    else:
        used_paid = paid_releases.get(str(curr_gw), False) if curr_gw > 0 else False

    if is_pre_deadline:
        refund = int(math.ceil(player_obj.get("buy_price", 0) / 2))
        release_type = "unlimited"
    elif not used_paid:
        refund = int(math.ceil(player_obj.get("buy_price", 0) / 2))
        release_type = "paid"
    else:
        refund = 0
        release_type = "free"

    # Execute release
    participant["squad"] = [p for p in participant["squad"] if p["name"] != req.player_name]
    participant["budget"] = float(participant.get("budget", 0)) + refund

    if release_type == "paid":
        participant.setdefault("paid_releases", {})[str(curr_gw)] = True

    room.setdefault("unsold_players", []).append(req.player_name)

    timestamp = _get_ist_now().strftime("%d-%b %H:%M")
    room.setdefault("trade_log", []).append({
        "time": timestamp,
        "msg": f"🗑️ Released: **{req.player_name}** by **{req.participant_name}** (Refund: {refund}M)"
    })
    _firebase_put(data)
    return {"message": f"Released {req.player_name}", "refund": refund, "type": release_type}


# ----------------------------------------------------------
# 21.  POST /auction/calculate-scores
# ----------------------------------------------------------
@app.post("/auction/calculate-scores")
async def calculate_scores(req: CalculateScoresRequest):
    """Admin scrapes Cricbuzz URL and stores scores for the GW."""
    data = _firebase_get()
    room = data.get("rooms", {}).get(req.room_code)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    if room.get("admin") != req.admin_name:
        raise HTTPException(status_code=403, detail="Admin only")

    gw = req.gameweek or room.get("current_gameweek", 1)
    gw_key = str(gw)

    try:
        players_data = scraper.fetch_match_data(req.cricbuzz_url)
        if not players_data:
            raise HTTPException(status_code=404, detail="No player data found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scraping failed: {e}")

    # Calculate scores
    gw_scores = room.get("gameweek_scores", {})
    existing = gw_scores.get(gw_key, {})

    for p in players_data:
        score = calculator.calculate_score(p)
        name = p["name"]
        existing[name] = existing.get(name, 0) + round(score)

    gw_scores[gw_key] = existing
    room["gameweek_scores"] = gw_scores
    _firebase_put(data)

    # Return the scores
    results = [{"name": k, "points": v} for k, v in sorted(existing.items(), key=lambda x: -x[1])]
    return {"message": f"Scores calculated for GW{gw}", "gameweek": gw, "scores": results[:20]}


# ----------------------------------------------------------
# 22.  POST /auction/import-squads
# ----------------------------------------------------------
@app.post("/auction/import-squads")
async def import_squads(req: ImportSquadsRequest):
    """
    Admin imports squads for participants and generates claim codes.
    Creates participants if they don't exist, assigns squads, and
    generates unique 4-char claim codes for each participant.
    
    Request body squads format:
    {"Alice": [{"name": "Virat Kohli", "role": "Batsman", "team": "RCB", "buy_price": 20}], ...}
    """
    data = _firebase_get()
    room = data.get("rooms", {}).get(req.room_code)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    if room.get("admin") != req.admin_name:
        raise HTTPException(status_code=403, detail="Admin only")

    participants = room.get("participants", [])
    existing_names = {p["name"] for p in participants}
    tournament_type = room.get("tournament_type", "t20_wc")
    budget = _DEFAULT_BUDGET.get(tournament_type, 200)

    claim_codes = room.get("claim_codes", {})
    used_codes = set(claim_codes.values())
    results = {}

    for p_name, squad_list in req.squads.items():
        # Create participant if doesn't exist
        if p_name not in existing_names:
            participants.append({
                "name": p_name,
                "budget": budget,
                "squad": [],
                "eliminated": False,
            })
            existing_names.add(p_name)

        # Find and update squad
        participant = next(p for p in participants if p["name"] == p_name)
        participant["squad"] = squad_list

        # Calculate spent budget or use custom provided budget
        if req.budgets and p_name in req.budgets:
            participant["budget"] = req.budgets[p_name]
        else:
            total_spent = sum(pl.get("buy_price", 0) for pl in squad_list)
            participant["budget"] = budget - total_spent

        # Generate unique 4-char claim code
        if p_name not in claim_codes:
            code = _generate_claim_token(4).upper()
            while code in used_codes:
                code = _generate_claim_token(4).upper()
            claim_codes[p_name] = code
            used_codes.add(code)

        results[p_name] = {
            "squad_size": len(squad_list),
            "budget_remaining": participant["budget"],
            "claim_code": claim_codes[p_name],
        }

    room["participants"] = participants
    room["claim_codes"] = claim_codes
    _firebase_put(data)
    return {"message": f"Imported squads for {len(req.squads)} participants", "details": results}


# ----------------------------------------------------------
# 22b. POST /auction/import-csv
# ----------------------------------------------------------
@app.post("/auction/import-csv")
async def import_csv(req: ImportCsvRequest, dry_run: bool = Query(False, description="Parse only, do not save")):
    """
    Admin uploads CSV text. Parses into squads.
    If dry_run=True, returns the parsed squads without saving.
    Otherwise, applies them to the database.
    """
    f = io.StringIO(req.csv_text.strip())
    reader = csv.reader(f)
    rows = list(reader)
    if not rows:
        raise HTTPException(status_code=400, detail="Empty CSV")

    # Load ipl squads for matching
    import difflib
    squads_path = Path(__file__).parent / "ipl_2026_squads.json"
    player_lookup = {}
    if squads_path.exists():
        with open(squads_path) as sp:
            ipl_data = json.load(sp)
            for team_data in ipl_data.get("teams", {}).values():
                for pl in team_data.get("squad", []):
                    player_lookup[pl["name"].lower()] = pl
    
    valid_names = list(player_lookup.keys())

    def match_player(raw_name):
        n = raw_name.lower().strip()
        if not n: return raw_name, "Unknown", "Unknown", []
        
        # Suggestions (Top 5)
        matches = difflib.get_close_matches(n, valid_names, n=5, cutoff=0.5)
        suggestions = []
        for m in matches:
            suggestions.append({
                "name": player_lookup[m]["name"],
                "role": player_lookup[m]["role"],
                "team": player_lookup[m].get("ipl_team", "Unknown")
            })

        if n in player_lookup:
            p = player_lookup[n]
            return p["name"], p["role"], p.get("ipl_team", "Unknown"), suggestions
            
        if matches:
            p = player_lookup[matches[0]]
            # If match is very close (e.g. > 0.9), return it as primary
            return p["name"], p["role"], p.get("ipl_team", "Unknown"), suggestions

        return raw_name, "Unknown", "Unknown", suggestions

    squads = {}
    custom_budgets = {}
    
    # Format A (Visual grid) 
    if len(rows) > 0 and (len(rows) < 2 or rows[1].count('') >= len(rows[1])-1 or "Participant" not in rows[0]):
        participants = {}
        header_row = rows[0]
        for i, name in enumerate(header_row):
            if name.strip():
                participants[i] = name.strip()
                squads[name.strip()] = []
        
        # Parse players
        for i, row in enumerate(rows[2:]):
            row_idx = i + 2
            # Is this the "budget" row? Row 27 (0-indexed 26) 
            if row_idx == 26: 
                for col_idx, p_name in participants.items():
                    if col_idx < len(row):
                        b_str = row[col_idx].strip()
                        if b_str:
                            try:
                                custom_budgets[p_name] = int(b_str.replace(',', '').replace('$', ''))
                            except ValueError: pass
                continue

            for col_idx, p_name in participants.items():
                if col_idx < len(row) and col_idx + 1 < len(row):
                    player = row[col_idx].strip()
                    price_str = row[col_idx+1].strip()
                    if player and price_str:
                        try:
                            price = int(price_str.replace(',', '').replace('$', ''))
                            m_name, m_role = match_player(player)
                            squads[p_name].append({"name": m_name, "price": price, "buy_price": price, "role": m_role})
                        except ValueError:
                            pass
    else:
        # Format B (Tabular: Participant, Player, ..., Price)
        headers = [h.strip().lower() for h in rows[0]]
        try:
            p_idx = headers.index("participant")
            pl_idx = headers.index("player")
            pr_idx = headers.index("price")
        except ValueError:
            raise HTTPException(status_code=400, detail="CSV tabular missing Participant/Player/Price columns")
            
        for row in rows[1:]:
            if len(row) > max(p_idx, pl_idx, pr_idx):
                p_name = row[p_idx].strip()
                player = row[pl_idx].strip()
                price_str = row[pr_idx].strip()
                if p_name and player and price_str:
                    if p_name not in squads:
                        squads[p_name] = []
                    try:
                        price = int(price_str.replace(',', '').replace('$', ''))
                        m_name, m_role = match_player(player)
                        squads[p_name].append({"name": m_name, "price": price, "buy_price": price, "role": m_role})
                    except ValueError:
                        pass

    if dry_run:
        return {"message": "Dry run successful", "squads": squads, "budgets": custom_budgets}

    # Now re-use import squads logic
    import_req = ImportSquadsRequest(room_code=req.room_code, admin_name=req.admin_name, squads=squads, budgets=custom_budgets)
    return await import_squads(import_req)


# ----------------------------------------------------------
# 23.  POST /auction/claim-with-code
# ----------------------------------------------------------
class ClaimWithCodeRequest(BaseModel):
    room_code: str
    claim_code: str
    uid: str

@app.post("/auction/claim-with-code")
async def claim_with_code(req: ClaimWithCodeRequest):
    """
    Participant claims their team using the 4-char PIN code.
    Links their Firebase UID to the participant.
    """
    data = _firebase_get()
    room = data.get("rooms", {}).get(req.room_code)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    claim_codes = room.get("claim_codes", {})
    # Find participant by claim code
    p_name = None
    for name, code in claim_codes.items():
        if code == req.claim_code.strip().upper():
            p_name = name
            break

    if not p_name:
        raise HTTPException(status_code=400, detail="Invalid claim code")

    # Check if already claimed
    room_user_map = data.get("room_user_map", {}).get(req.room_code, {})
    existing_uid = room_user_map.get(p_name)
    if existing_uid and existing_uid != req.uid:
        raise HTTPException(status_code=409, detail="This team has already been claimed by another user")

    # Link UID
    _auto_link_uid(data, req.room_code, p_name, req.uid, is_admin=(room.get("admin") == p_name))
    _firebase_put(data)
    return {"message": f"Successfully claimed team '{p_name}'", "participant_name": p_name}


# ----------------------------------------------------------
# 24.  GET /auction/schedule
# ----------------------------------------------------------
@app.get("/auction/schedule")
async def get_schedule(room_code: str = Query(...)):
    """Returns the IPL 2026 match schedule."""
    schedule_path = Path(__file__).parent / "ipl_2026_schedule.json"
    if not schedule_path.exists():
        raise HTTPException(status_code=404, detail="Schedule file not found")
    try:
        with open(schedule_path) as f:
            schedule = json.load(f)
        return schedule
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ----------------------------------------------------------
# 25.  GET /auction/ipl-squads
# ----------------------------------------------------------
@app.get("/auction/ipl-squads")
async def get_ipl_squads():
    """Returns all IPL 2026 team squads from local JSON."""
    squads_path = Path(__file__).parent / "ipl_2026_squads.json"
    if not squads_path.exists():
        raise HTTPException(status_code=404, detail="IPL squads file not found")
    try:
        with open(squads_path) as f:
            squads = json.load(f)
        return squads
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ----------------------------------------------------------
# 26.  GET /auction/trade-log
# ----------------------------------------------------------
@app.get("/auction/trade-log")
async def get_trade_log(room_code: str = Query(...)):
    """Returns the trade/transaction log for a room."""
    data = _firebase_get()
    room = data.get("rooms", {}).get(room_code)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    return {"trade_log": room.get("trade_log", []), "pending_trades": room.get("pending_trades", [])}


# ----------------------------------------------------------
# 27.  GET /auction/standings (enhanced with Best-11)
# ----------------------------------------------------------
@app.get("/auction/standings")
async def get_standings(
    room_code: str = Query(...),
    gameweek: Optional[int] = Query(None, description="Specific GW, or None for cumulative"),
):
    """
    Returns standings with proper Best-11 selection using role constraints.
    WK: 1-3, BAT: 1-4, AR: 3-6, BWL: 2-4
    """
    import itertools
    data = _firebase_get()
    room = data.get("rooms", {}).get(room_code)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    gw_scores_all = room.get("gameweek_scores", {})
    if not gw_scores_all:
        return {"standings": [], "message": "No scores yet"}

    # Load player role lookup
    squads_file = Path(__file__).parent / "ipl_2026_squads.json"
    player_role_lookup = {}
    if squads_file.exists():
        with open(squads_file) as f:
            squads_data = json.load(f)
        for team_data in squads_data.get("teams", {}).values():
            for pl in team_data.get("squad", []):
                player_role_lookup[pl["name"]] = pl.get("role", "Batsman")

    def categorize_role(role_str):
        role_str = (role_str or "").lower()
        if "wk" in role_str or "wicket" in role_str or "keeper" in role_str:
            return "WK"
        if "allrounder" in role_str or "all-rounder" in role_str or "all rounder" in role_str:
            return "AR"
        if "bowl" in role_str:
            return "BWL"
        return "BAT"

    def get_best_11(squad, player_scores, ir_player=None):
        if len(squad) < 19:
            ir_player = None
        active = [p for p in squad if (p["name"] if isinstance(p, dict) else p) != ir_player]
        scored = []
        for p in active:
            name = p["name"] if isinstance(p, dict) else p
            role_str = (p.get("role", "") if isinstance(p, dict) else "")
            if not role_str:
                role_str = player_role_lookup.get(name, "Batsman")
            cat = categorize_role(role_str)
            scored.append({"name": name, "category": cat, "score": player_scores.get(name, 0)})
        if len(scored) <= 11:
            return scored
        scored.sort(key=lambda x: x["score"], reverse=True)

        valid_ranges = {"WK": (1, 3), "BAT": (1, 4), "AR": (3, 6), "BWL": (2, 4)}
        best_team, best_score = [], -1
        for team in itertools.combinations(scored, 11):
            counts = {"WK": 0, "BAT": 0, "AR": 0, "BWL": 0}
            total = 0
            for p in team:
                counts[p["category"]] += 1
                total += p["score"]
            if all(lo <= counts[r] <= hi for r, (lo, hi) in valid_ranges.items()):
                if total > best_score:
                    best_score = total
                    best_team = list(team)
        return best_team if best_team else scored[:11]

    # Build standings
    standings = []
    active_participants = [p for p in room.get("participants", []) if not p.get("eliminated", False)]

    if gameweek is not None:
        # Single GW view
        gw_key = str(gameweek)
        scores = dict(gw_scores_all.get(gw_key, {}))
        bonuses = room.get("hattrick_bonuses", {}).get(gw_key, {})
        for pl, b in bonuses.items():
            scores[pl] = scores.get(pl, 0) + b

        locked = room.get("gameweek_squads", {}).get(gw_key, {})
        for p in active_participants:
            sq_data = locked.get(p["name"])
            if sq_data:
                squad = sq_data.get("squad", sq_data) if isinstance(sq_data, dict) else sq_data
                ir = sq_data.get("injury_reserve") if isinstance(sq_data, dict) else None
            else:
                squad = p["squad"]
                ir = p.get("injury_reserve")
            best = get_best_11(squad, scores, ir)
            total = sum(x["score"] for x in best)
            standings.append({"participant": p["name"], "points": total, "best_11": [x["name"] for x in best]})
    else:
        # Cumulative
        p_totals = {p["name"]: 0.0 for p in active_participants}
        for gw, scores in gw_scores_all.items():
            scores_with_bonus = dict(scores)
            bonuses = room.get("hattrick_bonuses", {}).get(gw, {})
            for pl, b in bonuses.items():
                scores_with_bonus[pl] = scores_with_bonus.get(pl, 0) + b
            locked = room.get("gameweek_squads", {}).get(str(gw), {})
            for p in active_participants:
                sq_data = locked.get(p["name"])
                if sq_data:
                    squad = sq_data.get("squad", sq_data) if isinstance(sq_data, dict) else sq_data
                    ir = sq_data.get("injury_reserve") if isinstance(sq_data, dict) else None
                else:
                    squad = p["squad"]
                    ir = p.get("injury_reserve")
                best = get_best_11(squad, scores_with_bonus, ir)
                p_totals[p["name"]] += sum(x["score"] for x in best)
        for name, pts in p_totals.items():
            standings.append({"participant": name, "points": pts})

    standings.sort(key=lambda x: -x["points"])
    for i, s in enumerate(standings):
        s["rank"] = i + 1

    return {"standings": standings, "gameweek": gameweek, "total_gameweeks": list(gw_scores_all.keys())}


# ----------------------------------------------------------
# 28.  POST /auction/set-deadline
# ----------------------------------------------------------
@app.post("/auction/set-deadline")
async def set_deadline(req: SetDeadlineRequest):
    """Admin sets bidding deadline for current GW as an ISO datetime."""
    data = _firebase_get()
    room = data.get("rooms", {}).get(req.room_code)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    if room.get("admin") != req.admin_name:
        raise HTTPException(status_code=403, detail="Admin only")

    try:
        dt = datetime.fromisoformat(req.deadline_iso)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ISO datetime format")

    room["bidding_deadline"] = dt.isoformat()
    room["game_phase"] = "Bidding"
    _firebase_put(data)
    return {"message": f"Deadline set to {dt.isoformat()}", "deadline": dt.isoformat()}


# ----------------------------------------------------------
# 29.  POST /auction/set-injury-reserve
# ----------------------------------------------------------
@app.post("/auction/set-injury-reserve")
async def set_injury_reserve(req: SetInjuryReserveRequest):
    """Participant sets their injury reserve player."""
    data = _firebase_get()
    room = data.get("rooms", {}).get(req.room_code)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    participant = next(
        (p for p in room.get("participants", []) if p["name"] == req.participant_name),
        None,
    )
    if not participant:
        raise HTTPException(status_code=404, detail="Participant not found")

    # Check player is in their squad
    in_squad = any(pl.get("name") == req.player_name for pl in participant.get("squad", []))
    if not in_squad:
        raise HTTPException(status_code=400, detail="Player not in your squad")

    participant["injury_reserve"] = req.player_name
    _firebase_put(data)
    return {"message": f"Injury reserve set to {req.player_name}"}


# ----------------------------------------------------------
# 30.  POST /auction/eliminate
# ----------------------------------------------------------
@app.post("/auction/eliminate")
async def eliminate_participants(req: EliminateRequest):
    """
    Admin triggers elimination based on IPL playoff structure:
    - GW 10 (after league stage): Top 4 survive, rest eliminated
    - GW 11 (after Q1+Eliminator): Top 3 survive
    - GW 12 (after Q2): Top 2 survive
    - GW 13 (after Final): Champion determined

    Eliminated participants' players are released back to the pool.
    """
    data = _firebase_get()
    room = data.get("rooms", {}).get(req.room_code)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    if room.get("admin") != req.admin_name:
        raise HTTPException(status_code=403, detail="Admin only")

    curr_gw = room.get("current_gameweek", 1)

    # Determine how many survive this round
    survive_map = {
        10: 4,   # After league stage: top 4
        11: 3,   # After Q1+Eliminator: top 3
        12: 2,   # After Q2: top 2
        13: 1,   # After Final: champion
    }
    survive_count = survive_map.get(curr_gw)
    if survive_count is None:
        raise HTTPException(
            status_code=400,
            detail=f"Elimination not applicable for GW{curr_gw}. Valid: GW 10-13.",
        )

    # Calculate standings from accumulated scores
    gw_scores_all = room.get("gameweek_scores", {})
    active_participants = [
        p for p in room.get("participants", []) if not p.get("eliminated", False)
    ]

    # Calculate cumulative points
    p_totals = {}
    for p in active_participants:
        p_totals[p["name"]] = 0.0
        for gw, scores in gw_scores_all.items():
            locked = room.get("gameweek_squads", {}).get(str(gw), {})
            sq_data = locked.get(p["name"])
            if sq_data:
                squad = sq_data.get("squad", sq_data) if isinstance(sq_data, dict) else sq_data
                ir = sq_data.get("injury_reserve") if isinstance(sq_data, dict) else None
            else:
                squad = p.get("squad", [])
                ir = p.get("injury_reserve")
            # Simple best-11 (top 11 by score, exclude IR)
            squad_scores = []
            for pl in squad:
                name = pl["name"] if isinstance(pl, dict) else pl
                if name == ir:
                    continue
                squad_scores.append(scores.get(name, 0))
            squad_scores.sort(reverse=True)
            p_totals[p["name"]] += sum(squad_scores[:11])

    # Sort by points descending
    ranked = sorted(p_totals.items(), key=lambda x: -x[1])
    survivors = set(name for name, _ in ranked[:survive_count])
    eliminated_names = []

    for p in room.get("participants", []):
        if p.get("eliminated", False):
            continue
        if p["name"] not in survivors:
            p["eliminated"] = True
            eliminated_names.append(p["name"])
            # Release their players back to the pool
            for pl in p.get("squad", []):
                room.setdefault("unsold_players", []).append(pl.get("name", ""))
            p["squad"] = []

    phase_names = {10: "League Stage", 11: "Qualifier 1 + Eliminator",
                   12: "Qualifier 2", 13: "Final"}
    phase_name = phase_names.get(curr_gw, f"GW{curr_gw}")

    if curr_gw == 13:
        winner = ranked[0][0] if ranked else "Unknown"
        room["champion"] = winner
        room["tournament_phase"] = "completed"
        message = f"🏆 {winner} is the CHAMPION! Final standings determined."
    else:
        room["tournament_phase"] = phase_name.lower().replace(" ", "_")
        message = f"Elimination after {phase_name}: {len(eliminated_names)} eliminated, {survive_count} survive"

    _firebase_put(data)
    return {
        "message": message,
        "eliminated": eliminated_names,
        "survivors": list(survivors),
        "gameweek": curr_gw,
    }


# ----------------------------------------------------------
# 31.  GET /auction/available-players
# ----------------------------------------------------------
@app.get("/auction/available-players")
async def available_players(room_code: str = Query(...)):
    """Returns players NOT owned by any participant (available for bidding)."""
    data = _firebase_get()
    room = data.get("rooms", {}).get(room_code)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    # Collect all owned player names
    owned = set()
    for p in room.get("participants", []):
        for sq_pl in p.get("squad", []):
            owned.add(sq_pl.get("name", ""))

    # Load IPL squads JSON as pool
    squads_path = Path(__file__).parent / "ipl_2026_squads.json"
    available = []
    if squads_path.exists():
        with open(squads_path) as f:
            squads_data = json.load(f)
        for team_data in squads_data.get("teams", {}).values():
            for pl in team_data.get("squad", []):
                if pl.get("name") not in owned:
                    available.append({
                        "name": pl.get("name"),
                        "role": pl.get("role", "Unknown"),
                        "team": pl.get("team", "Unknown"),
                    })

    available.sort(key=lambda x: x["name"])
    return {"available_players": available, "total": len(available)}


# ----------------------------------------------------------
# Run with: uvicorn api_server:app --port 8000 --reload
# ----------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api_server:app", host="0.0.0.0", port=8000, reload=True)

