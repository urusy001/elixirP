from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import Field, BaseModel


class CartBase(BaseModel):
    """Common fields for Cart (excluding PK and FKs)."""
    total: Decimal = Field(Decimal("0.00"), description="Total cart amount")
    last_updated: datetime = Field(..., description="Last time the cart was updated")


class CartCreate(CartBase):
    """Schema used when creating a new cart."""
    tg_id: int = Field(..., description="Telegram user ID that owns this cart")
    bag_id: int = Field(..., description="Bag associated with this cart")


class CartUpdate(BaseModel):
    """Schema used when updating an existing cart."""
    tg_id: int | None = None
    bag_id: int | None = None
    total: Decimal | None = None
    last_updated: datetime | None = None


class CartRead(CartBase):
    """Schema used when returning a cart from the database."""
    id: int
    tg_id: int
    bag_id: int

    model_config = {
        "from_attributes": True
    }
