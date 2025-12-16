from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field

from src.webapp.schemas.cart_item import CartItemRead


class CartBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_active: bool = True
    name: str | None = ''

    # matches SQLAlchemy Numeric(8, 2)
    sum: Decimal | None = 0.00
    delivery_sum: Decimal | None = 0.00
    delivery_string: str = "Не указан"
    commentary: str | None = None


class CartCreate(CartBase):
    user_id: int
    # if you want to enforce providing sums at creation, remove the `| None`
    sum: Decimal
    delivery_sum: Decimal


class CartUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_active: bool | None = None
    name: str | None = None

    sum: Decimal | None = None
    delivery_sum: Decimal | None = None
    delivery_string: str | None = None
    commentary: str | None = None


class CartRead(CartBase):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int
    user_id: int
    name: str

    sum: Decimal
    delivery_sum: Decimal
    delivery_string: str
    commentary: str | None = None

    created_at: datetime
    updated_at: datetime

    items: list[CartItemRead] = Field(default_factory=list)