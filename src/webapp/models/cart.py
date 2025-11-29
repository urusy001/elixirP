from sqlalchemy import (
    BigInteger,
    Numeric,
    Column,
    ForeignKey,
    DateTime,
    func,
)
from sqlalchemy.orm import relationship

from src.webapp.database import Base


class Cart(Base):
    __tablename__ = "carts"

    id = Column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        index=True,
        nullable=False,
    )

    # Owner (Telegram user)
    tg_id = Column(
        BigInteger,
        ForeignKey("users.tg_id"),
        nullable=False,
        index=True,
    )

    # Aggregates (optional: you can recompute from bags/items)
    total = Column(Numeric(10, 2), nullable=False, default=0.00)

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

    # Relationships
    user = relationship(
        "User",
        back_populates="carts",
    )

    # One cart → many bags
    bags = relationship(
        "Bag",
        back_populates="cart",
        cascade="all, delete-orphan",
    )