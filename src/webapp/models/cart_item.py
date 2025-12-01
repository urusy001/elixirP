# cart_item.py
from sqlalchemy import BigInteger, Column, DateTime, String, ForeignKey, func, Integer
from sqlalchemy.orm import relationship

from src.webapp.database import Base


class CartItem(Base):
    __tablename__ = "cart_items"

    id = Column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        index=True,
        nullable=False,
    )

    cart_id = Column(
        BigInteger,
        ForeignKey("carts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    product_onec_id = Column(
        String,
        ForeignKey("products.onec_id", ondelete="CASCADE"),  # 👈 тут
        nullable=False,
        index=True,
    )

    feature_onec_id = Column(
        String,
        ForeignKey("features.onec_id", ondelete="CASCADE"),  # 👈 и тут
        nullable=False,
        index=True,
    )

    quantity = Column(Integer, nullable=False, default=1)

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

    # ---------- relationships ----------

    cart = relationship("Cart", back_populates="items")

    product = relationship(
        "Product",
        back_populates="cart_items",
        foreign_keys=[product_onec_id],
        lazy="selectin",
    )

    feature = relationship(
        "Feature",
        back_populates="cart_items",
        foreign_keys=[feature_onec_id],
        lazy="selectin",
    )