from __future__ import annotations

from sqlalchemy import Column, Integer, String, DateTime, func, Table, ForeignKey
from sqlalchemy.orm import relationship

from src.webapp.database import Base

# Association table: Product(onec_id) <-> TgCategory(id)
product_tg_categories = Table(
    "product_tg_categories",
    Base.metadata,
    Column(
        "product_onec_id",
        String,
        ForeignKey("products.onec_id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "tg_category_id",
        Integer,
        ForeignKey("tg_categories.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class TgCategory(Base):
    __tablename__ = "tg_categories"

    id = Column(Integer, primary_key=True, autoincrement=True)

    name = Column(String(255), nullable=False, unique=True, index=True)
    description = Column(String, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        index=True,
    )

    products = relationship(
        "Product",
        secondary=product_tg_categories,
        back_populates="tg_categories",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<TgCategory id={self.id} name={self.name!r}>"