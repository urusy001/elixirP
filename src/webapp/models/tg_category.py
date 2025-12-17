from __future__ import annotations

from sqlalchemy import Column, Integer, String, DateTime, func
from sqlalchemy.orm import relationship

from src.webapp.database import Base
from src.webapp.models.product_tg_categories import product_tg_categories


class TgCategory(Base):
    __tablename__ = "tg_categories"

    id = Column(Integer, primary_key=True, autoincrement=True)

    name = Column(String(255), nullable=False, unique=True, index=True)
    description = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now(), index=True)

    products = relationship(
        "Product",
        secondary=product_tg_categories,
        back_populates="tg_categories",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<TgCategory id={self.id} name={self.name!r}>"