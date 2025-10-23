from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship

from src.webapp.database import Base

class Unit(Base):
    __tablename__ = "units"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    onec_id = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)

    categories = relationship("Category", back_populates="unit", cascade="all, delete-orphan")
