from sqlalchemy import Column, ForeignKey, BigInteger, String
from sqlalchemy.orm import relationship

from src.webapp.database import Base


class Bag(Base):
    __tablename__ = "bags"

    id = Column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        index=True,
        nullable=False,
    )

    # Link to cart
    cart_id = Column(
        BigInteger,
        ForeignKey("carts.id"),
        nullable=False,
        index=True,
    )

    # Meta (e.g. “Main cart”, “Gift for X”, etc.)
    name = Column(
        String(64),
        nullable=True,
        default="Корзина",
    )

    # Relationships
    cart = relationship(
        "Cart",
        back_populates="bags",
    )

    # Bag items in this bag
    items = relationship(
        "BagItem",
        back_populates="bag",
        cascade="all, delete-orphan",
    )