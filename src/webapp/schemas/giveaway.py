from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from src.webapp.schemas.participant import ParticipantRead  # avoid circular imports

class GiveawayBase(BaseModel):
    name: str
    prize: dict
    description: Optional[str] = None
    start_date: Optional[datetime] = Field(default_factory=datetime.utcnow)
    end_date: Optional[datetime] = None


class GiveawayCreate(GiveawayBase):
    pass

class GiveawayUpdate(BaseModel):
    name: Optional[str] = None
    prize: Optional[str] = None
    description: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class GiveawayRead(GiveawayBase):
    id: int
    participants: List[ParticipantRead] = []

    class Config:
        orm_mode = True