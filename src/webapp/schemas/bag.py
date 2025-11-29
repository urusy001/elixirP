from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, ConfigDict

from src.webapp.schemas.bag_item import BagItemRead


class BagBase(BaseModel):
    name: Optional[str] = None


class BagCreate(BagBase):
    cart_id: int


class BagUpdate(BaseModel):
    name: Optional[str] = None


class BagRead(BagBase):
    id: int
    cart_id: int
    items: list[BagItemRead] = []

    model_config = ConfigDict(from_attributes=True)