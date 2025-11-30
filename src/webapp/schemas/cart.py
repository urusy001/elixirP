from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict

from src.webapp.schemas.cart_item import CartItemRead


class CartBase(BaseModel):
    is_active: bool = True


class CartCreate(CartBase):
    user_id: int


class CartUpdate(BaseModel):
    is_active: Optional[bool] = None
    name: Optional[str] = None


class CartRead(CartBase):
    id: int
    user_id: int
    name: str
    created_at: datetime
    updated_at: datetime
    items: list[CartItemRead] = []

    model_config = ConfigDict(from_attributes=True)