from pydantic import BaseModel

# Shared fields
class UnitBase(BaseModel):
    onec_id: str
    name: str
    description: str

# For creating a new unit
class UnitCreate(UnitBase):
    pass

# For updating an existing unit (all fields optional for partial updates)
class UnitUpdate(BaseModel):
    onec_id: str | None = None
    name: str | None = None
    description: str | None = None

# For reading from DB (includes ID)
class UnitRead(UnitBase):
    id: int

    class Config:
        from_attributes = True