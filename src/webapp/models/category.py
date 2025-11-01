from sqlalchemy import Column, Integer, String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from src.webapp.database import Base


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    onec_id = Column(String, nullable=False, unique=True)
    unit_onec_id = Column(String, ForeignKey("units.onec_id", ondelete="CASCADE"))
    name = Column(String, nullable=False)
    code = Column(String, nullable=True)

    unit = relationship("Unit", back_populates="categories")
    products = relationship("Product", back_populates="category", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("onec_id", "unit_onec_id", name="uix_onec_unit"),
    )
