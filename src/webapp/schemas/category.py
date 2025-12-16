from __future__ import annotations
from pydantic import BaseModel

# Shared fields
class CategoryBase(BaseModel):
    onec_id: str
    unit_onec_id: str | None = None
    name: str
    code: str | None = None  # optional


# For creating a new category
class CategoryCreate(CategoryBase):
    pass


# For updating an existing category
class CategoryUpdate(CategoryBase):
    onec_id: str | None = None
    unit_onec_id: str | None = None
    name: str | None = None
    code: str | None = None


# For reading from DB (includes ID)
class CategoryRead(CategoryBase):
    id: int

    class Config:
        from_attributes = True
