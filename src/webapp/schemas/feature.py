from typing import Optional

from pydantic import BaseModel


class FeatureBase(BaseModel):
    onec_id: str
    product_onec_id: str
    name: str
    code: str
    file_id: str
    price: float = 0
    balance: int = 0


class FeatureCreate(FeatureBase):
    pass


class FeatureUpdate(BaseModel):
    onec_id: Optional[str] = None
    product_onec_id: Optional[str] = None
    name: Optional[str] = None
    code: Optional[str] = None
    file_id: Optional[str] = None
    price: Optional[float] = None
    balance: Optional[int] = None


class FeatureRead(FeatureBase):
    id: int

    class Config:
        from_attributes = True
