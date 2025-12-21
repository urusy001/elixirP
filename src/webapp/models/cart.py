from __future__ import annotations

import random

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    event,
    func,
)
from sqlalchemy.orm import relationship

from src.webapp.database import Base


class Cart(Base):
    __tablename__ = "carts"

    id = Column(
        BigInteger,
        primary_key=True,
        autoincrement=False,
        index=True,
        nullable=False,
        default=lambda: random.randint(10**6, 10**7 - 1),
    )

    user_id = Column(
        BigInteger,
        ForeignKey("users.tg_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name = Column(String, nullable=True)

    sum = Column(Numeric(8, 2), nullable=False, default=0, server_default="0")
    delivery_sum = Column(Numeric(8, 2), nullable=False, default=0, server_default="0")

    # ✅ FK to promo_codes.code
    promo_code = Column(
        String(80),
        ForeignKey("promo_codes.code", ondelete="SET NULL"),
        nullable=True,
        default=None,
        index=True,
    )

    delivery_string = Column(String, nullable=False, default="Не указан", server_default="Не указан")
    commentary = Column(String, nullable=True)

    is_active = Column(Boolean, nullable=False, default=True, server_default="true", index=True)

    status = Column(String, nullable=True, default=None)
    yandex_request_id = Column(String, nullable=True, default=None)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now(), index=True)

    user = relationship("User", back_populates="carts")

    items = relationship(
        "CartItem",
        back_populates="cart",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # ✅ relationship to PromoCode via promo_code -> PromoCode.code
    promo = relationship(
        "PromoCode",
        back_populates="carts",
        foreign_keys=[promo_code],
        primaryjoin="Cart.promo_code == PromoCode.code",
        lazy="joined",
        uselist=False,
    )


@event.listens_for(Cart, "after_insert")
def set_cart_name(mapper, connection, target: Cart):
    # set default name only if not provided
    if target.name:
        return
    cart_name = f"Заказ #{target.id}"
    connection.execute(
        Cart.__table__.update().where(Cart.id == target.id).values(name=cart_name)
    )