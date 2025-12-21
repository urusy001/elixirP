from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PromoCodeBase(BaseModel):
    code: str = Field(..., min_length=1, max_length=80)

    owner_name: str = Field(..., min_length=1, max_length=255)
    owner_pct: Decimal = Field(default=Decimal("0.00"))
    owner_amount_gained: Decimal = Field(default=Decimal("0.00"))

    lvl1_name: Optional[str] = Field(default=None, max_length=255)
    lvl1_pct: Decimal = Field(default=Decimal("0.00"))
    lvl1_amount_gained: Decimal = Field(default=Decimal("0.00"))

    lvl2_name: Optional[str] = Field(default=None, max_length=255)
    lvl2_pct: Decimal = Field(default=Decimal("0.00"))
    lvl2_amount_gained: Decimal = Field(default=Decimal("0.00"))

    times_used: int = 0

    @field_validator("code", "owner_name")
    @classmethod
    def strip_required(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("must not be empty")
        return v

    @field_validator("lvl1_name", "lvl2_name")
    @classmethod
    def strip_optional(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip()
        return v or None

    @field_validator("times_used")
    @classmethod
    def nonneg_int(cls, v: int) -> int:
        if v < 0:
            raise ValueError("times_used must be >= 0")
        return v

    @field_validator("owner_pct", "lvl1_pct", "lvl2_pct")
    @classmethod
    def pct_range(cls, v: Decimal) -> Decimal:
        if v < 0 or v > 100:
            raise ValueError("percent must be between 0 and 100")
        return v

    @field_validator("owner_amount_gained", "lvl1_amount_gained", "lvl2_amount_gained")
    @classmethod
    def money_nonneg(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("amount must be >= 0")
        return v


class PromoCodeCreate(PromoCodeBase):
    pass


class PromoCodeUpdate(BaseModel):
    code: Optional[str] = Field(default=None, min_length=1, max_length=80)

    owner_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    owner_pct: Optional[Decimal] = None
    owner_amount_gained: Optional[Decimal] = None

    lvl1_name: Optional[str] = Field(default=None, max_length=255)
    lvl1_pct: Optional[Decimal] = None
    lvl1_amount_gained: Optional[Decimal] = None

    lvl2_name: Optional[str] = Field(default=None, max_length=255)
    lvl2_pct: Optional[Decimal] = None
    lvl2_amount_gained: Optional[Decimal] = None

    times_used: Optional[int] = None

    @field_validator("code", "owner_name")
    @classmethod
    def strip_required_if_present(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip()
        if not v:
            raise ValueError("must not be empty")
        return v

    @field_validator("lvl1_name", "lvl2_name")
    @classmethod
    def strip_optional(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip()
        return v or None

    @field_validator("times_used")
    @classmethod
    def nonneg_int(cls, v: Optional[int]) -> Optional[int]:
        if v is None:
            return None
        if v < 0:
            raise ValueError("times_used must be >= 0")
        return v

    @field_validator("owner_pct", "lvl1_pct", "lvl2_pct")
    @classmethod
    def pct_range(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is None:
            return None
        if v < 0 or v > 100:
            raise ValueError("percent must be between 0 and 100")
        return v

    @field_validator("owner_amount_gained", "lvl1_amount_gained", "lvl2_amount_gained")
    @classmethod
    def money_nonneg(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is None:
            return None
        if v < 0:
            raise ValueError("amount must be >= 0")
        return v


class PromoCodeOut(PromoCodeBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime