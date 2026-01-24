from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class TgCategoryMini(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str


class ProductMini(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    onec_id: str
    name: str
    code: str
    tg_categories: list[TgCategoryMini] = []


class FeatureMini(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    onec_id: str
    name: str
    code: str
    price: float  # Numeric/Decimal -> float


class CartItemWebRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cart_id: int
    product_onec_id: str
    feature_onec_id: str
    quantity: int
    created_at: datetime
    updated_at: datetime

    # ✅ отношения, чтобы фронт видел названия/цену
    product: Optional[ProductMini] = None
    feature: Optional[FeatureMini] = None


class CartWebRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: Optional[str] = None
    user_id: int

    status: Optional[str] = None

    sum: float
    delivery_sum: float
    delivery_string: str
    commentary: Optional[str] = None

    phone: str
    email: str

    is_active: bool
    is_paid: bool
    is_canceled: bool
    is_shipped: bool

    created_at: datetime
    updated_at: datetime

    # ✅ ВАЖНО: items всегда list
    items: list[CartItemWebRead] = []