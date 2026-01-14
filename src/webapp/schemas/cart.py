from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

from src.webapp.schemas.cart_item import CartItemRead

ZERO_MONEY = Decimal("0.00")


class PromoCodeRef(BaseModel):
    """Small nested promo view for cart responses (avoids circular imports)."""
    model_config = ConfigDict(from_attributes=True)

    code: str
    owner_name: str
    owner_pct: Decimal

    lvl1_name: Optional[str] = None
    lvl1_pct: Decimal

    lvl2_name: Optional[str] = None
    lvl2_pct: Decimal


class CartCreate(BaseModel):
    # Required by model
    user_id: int

    # Optional in model (name is auto-set after insert if None)
    name: Optional[str] = None

    # Money fields in model
    sum: Decimal = Field(default=ZERO_MONEY)
    delivery_sum: Decimal = Field(default=ZERO_MONEY)

    promo_code: Optional[str] = Field(default=None)
    promo_gains: Decimal = Field(default=ZERO_MONEY)
    promo_gains_given: bool = Field(default=False)

    delivery_string: str = Field(default="Не указан")
    commentary: Optional[str] = None

    # Status flags in model
    is_active: bool = True
    is_paid: bool = False
    is_canceled: bool = False
    is_shipped: bool = False

    status: Optional[str] = None
    yandex_request_id: Optional[str] = None


class CartUpdate(BaseModel):
    # PATCH-style: everything optional, so you don't accidentally reset fields
    name: Optional[str] = None

    sum: Optional[Decimal] = None
    delivery_sum: Optional[Decimal] = None

    promo_code: Optional[str] = None
    promo_gains: Optional[Decimal] = None
    promo_gains_given: Optional[bool] = None

    delivery_string: Optional[str] = None
    commentary: Optional[str] = None

    is_active: Optional[bool] = None
    is_paid: Optional[bool] = None
    is_canceled: Optional[bool] = None
    is_shipped: Optional[bool] = None

    status: Optional[str] = None
    yandex_request_id: Optional[str] = None


class CartRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int

    name: Optional[str] = None

    sum: Decimal
    delivery_sum: Decimal

    promo_code: Optional[str] = None
    promo_gains: Decimal
    promo_gains_given: bool

    # nested promo if relationship is loaded; else None
    promo: Optional[PromoCodeRef] = None

    delivery_string: str
    commentary: Optional[str] = None

    is_active: bool
    is_paid: bool
    is_canceled: bool
    is_shipped: bool

    status: Optional[str] = None
    yandex_request_id: Optional[str] = None

    created_at: datetime
    updated_at: datetime

    items: list[CartItemRead] = Field(default_factory=list)