from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict

class CartBase(BaseModel):
    tg_id: int


class CartCreate(CartBase):
    pass


class CartUpdate(BaseModel):
    # e.g. if you want to manually override total
    total: Optional[Decimal] = None


class CartRead(CartBase):
    id: int
    total: Decimal
    created_at: datetime
    updated_at: datetime
    bags: List[BagRead] = []

    model_config = ConfigDict(from_attributes=True)