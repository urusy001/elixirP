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

    # DB: nullable=True, but your after_insert sets it.
    # Keep it optional on input side; don't force user to send it.
    name: str | None = None

    # DB: Numeric(8,2) NOT NULL default 0
    sum: Decimal = Field(default=ZERO_MONEY)
    delivery_sum: Decimal = Field(default=ZERO_MONEY)
    yandex_request_id: int | None = None
    # DB: NOT NULL default "Не указан"
    delivery_string: str = "Не указан"

    # DB: nullable
    commentary: str | None = None


class CartCreate(BaseModel):
    """
    What client sends to create a cart.
    Usually: user_id only. Totals may be computed server-side.
    """
    model_config = ConfigDict(extra="forbid")

    user_id: int

    # Optional because DB has defaults.
    # If your API requires them, make them required by removing defaults.
    name: str | None = None
    is_active: bool = True
    sum: Decimal = Field(default=ZERO_MONEY)
    delivery_sum: Decimal = Field(default=ZERO_MONEY)
    delivery_string: str = "Не указан"
    commentary: str | None = None
    yandex_request_id: int | None = None


class CartUpdate(BaseModel):
    """
    PATCH payload: only fields that are provided should be updated.
    """
    model_config = ConfigDict(extra="forbid")

    is_active: bool | None = None
    name: str | None = None

    sum: Decimal | None = None
    delivery_sum: Decimal | None = None
    delivery_string: str | None = None
    yandex_request_id: int | None = None
    commentary: str | None = None


class CartRead(BaseModel):
    """
    What API returns.
    """
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    # DB: BigInteger
    id: int
    user_id: int

    # DB: nullable, but after_insert sets it — still safest to allow None
    name: str | None = None

    sum: Decimal
    delivery_sum: Decimal
    delivery_string: str
    commentary: str | None = None
    yandex_request_id: int | None = None
    is_active: bool

    created_at: datetime
    updated_at: datetime

    items: list[CartItemRead] = Field(default_factory=list)