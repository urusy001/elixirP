from pydantic import BaseModel
from datetime import date

class UserTokenUsageBase(BaseModel):
    user_id: int
    date: date
    input_tokens: int = 0
    output_tokens: int = 0

class UserTokenUsageCreate(UserTokenUsageBase):
    pass

class UserTokenUsageUpdate(BaseModel):
    input_tokens: int | None = None
    output_tokens: int | None = None

class UserTokenUsageRead(UserTokenUsageBase):
    id: int
    input_cost_usd: float
    output_cost_usd: float

    class Config:
        from_attributes = True