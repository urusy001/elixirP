from __future__ import annotations

from pydantic import BaseModel, Field


class BagItemBase(BaseModel):
    """Common fields for BagItem (excluding PK)."""

    product_id: int | None = Field(
        None,
        description="ID of the product in this bag item (nullable if not bound yet)",
    )
    quantity: int = Field(
        1,
        ge=1,
        description="Quantity of this product in the bag",
    )


# ---------- Create ----------

class BagItemCreate(BagItemBase):
    """Schema used when creating a new bag item."""
    bag_id: int = Field(..., description="ID of the bag this item belongs to")


# ---------- Update ----------

class BagItemUpdate(BaseModel):
    """Schema used when updating an existing bag item."""
    bag_id: int | None = Field(
        None,
        description="Bag ID (only change if you want to move the item to another bag)",
    )
    product_id: int | None = Field(
        None,
        description="Updated product ID",
    )
    quantity: int | None = Field(
        None,
        ge=1,
        description="Updated quantity",
    )


# ---------- Read ----------

class BagItemRead(BagItemBase):
    """Schema used when returning a bag item from the database."""
    id: int
    bag_id: int

    model_config = {
        "from_attributes": True  # enables ORM mode for SQLAlchemy BagItem
    }