from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, ConfigDict

class BagItemBase(BaseModel):
    product_id: int
    quantity: int = 1


class BagItemCreate(BagItemBase):
    bag_id: int


class BagItemUpdate(BaseModel):
    quantity: Optional[int] = None


class BagItemRead(BagItemBase):
    id: int

    model_config = ConfigDict(from_attributes=True)