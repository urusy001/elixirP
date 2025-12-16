from __future__ import annotations

from pydantic import BaseModel
from src.webapp.schemas.tg_category import TgCategoryRead


class ProductBase(BaseModel):
    onec_id: str
    category_onec_id: str
    name: str
    code: str
    description: str | None = None
    usage: str | None = None
    expiration: str | None = None


class ProductCreate(ProductBase): pass


class ProductUpdate(BaseModel):
    onec_id: str | None = None
    category_onec_id: str | None = None
    name: str | None = None
    code: str | None = None
    description: str | None = None
    usage: str | None = None
    expiration: str | None = None


class ProductRead(ProductBase):
    id: int

    # ✅ added
    tg_categories: list[TgCategoryRead] = []

    class Config:
        from_attributes = True