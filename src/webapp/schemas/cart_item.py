from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

class CartItemBase(BaseModel):
    product_onec_id: str
    feature_onec_id: str
    quantity: int


class CartItemCreate(CartItemBase):
    """What frontend sends when adding to cart."""
    pass


class CartItemUpdate(BaseModel):
    quantity: Optional[int] = None


class CartItemRead(CartItemBase):
    id: int
    cart_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)