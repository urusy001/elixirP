from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field

from src.webapp.schemas.cart_item import CartItemRead


# -------------------------
# Shared helpers
# -------------------------

ZERO_MONEY = Decimal("0.00")


class CartBase(BaseModel):
    """
    Mirrors DB columns (except id/user_id/timestamps/items).
    """
    model_config = ConfigDict(extra="forbid")

    is_active: bool = True
    status: str | None = None
    name: str | None = None
    sum: Decimal = Field(default=ZERO_MONEY)
    delivery_sum: Decimal = Field(default=ZERO_MONEY)
    yandex_request_id: str | None = None
    delivery_string: str = "Не указан"
    commentary: str | None = None


class CartCreate(BaseModel):
    """
    What client sends to create a cart.
    Usually: user_id only. Totals may be computed server-side.
    """
    model_config = ConfigDict(extra="forbid")

    user_id: int
    status: str | None = None
    name: str | None = None
    is_active: bool = True
    sum: Decimal = Field(default=ZERO_MONEY)
    delivery_sum: Decimal = Field(default=ZERO_MONEY)
    delivery_string: str = "Не указан"
    commentary: str | None = None
    yandex_request_id: str | None = None


class CartUpdate(BaseModel):
    """
    PATCH payload: only fields that are provided should be updated.
    """
    model_config = ConfigDict(extra="forbid")

    is_active: bool | None = None
    name: str | None = None
    status: str | None = None
    sum: Decimal | None = None
    delivery_sum: Decimal | None = None
    delivery_string: str | None = None
    yandex_request_id: str | None = None
    commentary: str | None = None


class CartRead(BaseModel):
    """
    What API returns.
    """
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: int
    user_id: int
    name: str | None = None
    status: str | None = None
    sum: Decimal
    delivery_sum: Decimal
    delivery_string: str
    commentary: str | None = None
    yandex_request_id: str | None = None
    is_active: bool

    created_at: datetime
    updated_at: datetime

    items: list[CartItemRead] = Field(default_factory=list)