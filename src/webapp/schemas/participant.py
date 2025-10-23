from typing import Optional
from pydantic import BaseModel

class ParticipantBase(BaseModel):
    tg_id: int
    ref_id: Optional[int] = None
    completed_subscription: bool = False
    completed_refs: bool = False
    completed_deal: bool = False
    deal_code: Optional[int] = None


class ParticipantCreate(ParticipantBase):
    giveaway_id: int


class ParticipantUpdate(BaseModel):
    completed_subscription: Optional[bool] = None
    completed_refs: Optional[bool] = None
    completed_deal: Optional[bool] = None
    deal_code: Optional[int] = None


class ParticipantRead(ParticipantBase):
    giveaway_id: int

    class Config:
        orm_mode = True