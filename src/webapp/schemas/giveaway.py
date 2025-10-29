from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from src.webapp.schemas.participant import ParticipantRead  # avoid circular imports


class GiveawayBase(BaseModel):
    name: str
    prize: Dict[str, Any]  # JSON field in DB, so should be dict here
    channel_username: str
    description: Optional[str] = None
    start_date: Optional[datetime] = Field(default_factory=datetime.utcnow)
    end_date: Optional[datetime] = None

    minimal_order_amount: Optional[float] = 0.0
    minimal_review_grade: Optional[int] = 4
    minimal_review_length: Optional[int] = 100
    minimal_referral_amount: Optional[int] = 3


class GiveawayCreate(GiveawayBase):
    pass


class GiveawayUpdate(BaseModel):
    name: Optional[str] = None
    prize: Optional[Dict[str, Any]] = None
    channel_username: Optional[str] = None
    description: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

    minimal_order_amount: Optional[float] = None
    minimal_review_grade: Optional[int] = None
    minimal_review_length: Optional[int] = None
    minimal_referral_amount: Optional[int] = None


class GiveawayRead(GiveawayBase):
    id: int
    participants: List[ParticipantRead] = []

    class Config:
        orm_mode = True