from __future__ import annotations

from pydantic import Field, BaseModel


class BagBase(BaseModel):
    """Common fields for Bag (excluding PK and FKs)."""
    name: str | None = Field("Корзина #X", max_length=32, description="Human-friendly bag name")
    note: str = Field("", description="Optional note attached to this bag")


class BagCreate(BagBase):
    """Schema used when creating a new bag."""
    tg_id: int = Field(..., description="Telegram user ID that owns this bag")
    cart_id: int = Field(..., description="Associated cart ID")


class BagUpdate(BaseModel):
    """Schema used when updating an existing bag."""
    name: str | None = None
    note: str | None = None
    tg_id: int | None = None
    cart_id: int | None = None


class BagRead(BagBase):
    """Schema used when returning a bag from the database."""
    id: int
    tg_id: int
    cart_id: int

    model_config = {
        "from_attributes": True
    }
