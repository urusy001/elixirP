from datetime import datetime
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field

from config import MOSCOW_TZ
from src.webapp.schemas.participant import ParticipantRead  # avoid circular imports


class GiveawayBase(BaseModel):
    name: str
    prize: Dict[str, Any]  # JSON in DB
    channel_username: str
    description: Optional[str] = None

    start_date: Optional[datetime] = Field(default_factory=lambda: datetime.now(MOSCOW_TZ))
    end_date: Optional[datetime] = None

    minimal_order_amount: Optional[float] = 0.0
    minimal_review_grade: Optional[int] = 4
    minimal_review_length: Optional[int] = 100
    minimal_referral_amount: Optional[int] = 3

    # текст при закрытии (можно задать сразу при создании)
    closed_message: Optional[str] = None


class GiveawayCreate(GiveawayBase):
    # closed флаг сам посчитаем на бэке
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

    closed_message: Optional[str] = None
    # если хочешь, чтобы можно было вручную закрыть/открыть:
    closed: Optional[bool] = None


class GiveawayRead(GiveawayBase):
    id: int
    closed: bool
    closed_message: Optional[str] = None
    participants: List[ParticipantRead] = []

    class Config:
        orm_mode = True