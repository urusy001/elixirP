from __future__ import annotations

from pydantic import BaseModel
from src.webapp.schemas.tg_category import TgCategoryRead


# Shared fields
class ProductBase(BaseModel):
    onec_id: str
    category_onec_id: str
    name: str
    code: str
    description: str | None = None
    usage: str | None = None
    expiration: str | None = None


# For creating a new product
class ProductCreate(ProductBase):
    pass


# For updating a product
class ProductUpdate(BaseModel):
    onec_id: str | None = None
    category_onec_id: str | None = None
    name: str | None = None
    code: str | None = None
    description: str | None = None
    usage: str | None = None
    expiration: str | None = None

    # ✅ added (optional) for bulk set/replace on backend if you want
    tg_category_ids: list[int] | None = None


# For reading from DB (includes ID)
class ProductRead(ProductBase):
    id: int

    # ✅ added
    tg_categories: list[TgCategoryRead] = []

    class Config:
        from_attributes = True