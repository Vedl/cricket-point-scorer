from typing import Optional, List
from sqlmodel import Field, SQLModel, Relationship
from datetime import datetime

class Participant(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    is_eliminated: bool = Field(default=False)
    
    squad: List["SquadPlayer"] = Relationship(back_populates="participant")

class Player(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    role: str = Field(default="Unknown") # WK, BAT, BWL, AR
    cricbuzz_profile_url: Optional[str] = Field(default=None)
    
    squad_entries: List["SquadPlayer"] = Relationship(back_populates="player")
    scores: List["PlayerScore"] = Relationship(back_populates="player")

class SquadPlayer(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    participant_id: int = Field(foreign_key="participant.id")
    player_id: int = Field(foreign_key="player.id")
    is_ir: bool = Field(default=False) # Injury Reserve (Inactive)
    
    participant: Optional[Participant] = Relationship(back_populates="squad")
    player: Optional[Player] = Relationship(back_populates="squad_entries")

class Match(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    gameweek: int = Field(index=True) # 1-9
    url: str
    status: str = Field(default="PENDING") # PENDING, PROCESSED
    processed_at: Optional[datetime] = Field(default=None)
    
    scores: List["PlayerScore"] = Relationship(back_populates="match")

class PlayerScore(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    player_id: int = Field(foreign_key="player.id")
    match_id: int = Field(foreign_key="match.id")
    
    points: int
    runs: int = 0
    wickets: int = 0
    catches: int = 0
    
    player: Optional[Player] = Relationship(back_populates="scores")
    match: Optional[Match] = Relationship(back_populates="scores")
