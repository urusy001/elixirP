from pydantic import BaseModel
from decimal import Decimal

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

# For reading from DB (includes ID)
class ProductRead(ProductBase):
    id: int

    class Config:
        from_attributes = True