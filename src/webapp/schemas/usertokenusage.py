from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel

BotLiteral = Literal["dose", "professor", "new"]


class UserTokenUsageBase(BaseModel):
    user_id: int
    date: date
    bot: BotLiteral
    input_tokens: int = 0
    output_tokens: int = 0


class UserTokenUsageCreate(UserTokenUsageBase):
    pass


class UserTokenUsageUpdate(BaseModel):
    bot: Optional[BotLiteral] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None


class UserTokenUsageRead(UserTokenUsageBase):
    id: int
    input_cost_usd: float
    output_cost_usd: float

    class Config:
        from_attributes = True
