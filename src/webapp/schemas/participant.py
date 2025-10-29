# src/webapp/schemas/participant.py
from typing import Optional
from pydantic import BaseModel


class ParticipantBase(BaseModel):
    tg_id: int
    ref_id: Optional[int] = None

    completed_subscription: bool = False
    completed_refs: bool = False
    completed_deal: bool = False
    completed_review: bool = False

    deal_code: Optional[int] = None

    # newly added review fields (read-only until we fetch a real review)
    review_id: Optional[int] = None
    review_email: Optional[str] = None
    review_phone: Optional[str] = None
    review_fullname: Optional[str] = None
    participation_code: Optional[str] = None


class ParticipantCreate(ParticipantBase):
    giveaway_id: int


class ParticipantUpdate(BaseModel):
    # all fields optional for PATCH / partial update
    ref_id: Optional[int] = None
    completed_subscription: Optional[bool] = None
    completed_refs: Optional[bool] = None
    completed_deal: Optional[bool] = None
    completed_review: Optional[bool] = None
    deal_code: Optional[int] = None

    # allow setting/clearing review fields from code
    review_id: Optional[int] = None
    review_email: Optional[str] = None
    review_phone: Optional[str] = None
    review_fullname: Optional[str] = None
    participation_code: Optional[str] = None


class ParticipantRead(ParticipantBase):
    giveaway_id: int

    class Config:
        orm_mode = True