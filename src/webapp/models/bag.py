from sqlalchemy import Column, ForeignKey, BigInteger, String
from sqlalchemy.orm import relationship

from src.webapp.database import Base


class Bag(Base):
    __tablename__ = "bags"

    id = Column(BigInteger, primary_key=True, autoincrement=True, index=True, nullable=False)

    # Owner
    tg_id = Column(BigInteger, ForeignKey("users.tg_id"), nullable=False, index=True)

    # Meta
    name = Column(String(32), nullable=True, default="Корзина #X")  # TODO: factory for names
    note = Column(String(1024), nullable=False, default="")

    # Relationships
    user = relationship(
        "User",
        back_populates="bags",
    )

    # Bag items in this bag
    items = relationship(
        "BagItem",
        back_populates="bag",
        cascade="all, delete-orphan",
    )

    # Carts that are associated with this bag (via Cart.bag_id)
    carts = relationship(
        "Cart",
        back_populates="bag",
        foreign_keys="Cart.bag_id",
    )