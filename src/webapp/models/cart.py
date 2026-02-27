import random

from datetime import datetime
from decimal import Decimal
from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Numeric, String, event, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.webapp.database import Base


class Cart(Base):
    __tablename__ = "carts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, index=True, nullable=False, default=lambda: random.randint(10**6, 10**7 - 1))
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.tg_id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    phone: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False)
    sum: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False, default=0, server_default="0")
    delivery_sum: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False, default=0, server_default="0")
    promo_code: Mapped[str | None] = mapped_column(String, ForeignKey("promo_codes.code", ondelete="SET NULL"), nullable=True, default=None, index=True)
    promo_gains: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False, default=0, server_default="0")
    promo_gains_given: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="FALSE")
    delivery_string: Mapped[str] = mapped_column(String, nullable=False, default="Не указан", server_default="Не указан")
    commentary: Mapped[str | None] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true", index=True)
    is_paid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false", index=True)
    is_canceled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false", index=True)
    is_shipped: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false", index=True)
    status: Mapped[str | None] = mapped_column(String, nullable=True, default=None)
    yandex_request_id: Mapped[str | None] = mapped_column(String, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now(), index=True)

    user: Mapped["User"] = relationship("User", back_populates="carts")
    items: Mapped[list["CartItem"]] = relationship("CartItem", back_populates="cart", cascade="all, delete-orphan", lazy="selectin")
    promo: Mapped["PromoCode"] = relationship("PromoCode", back_populates="carts", foreign_keys=[promo_code], primaryjoin="Cart.promo_code == PromoCode.code", lazy="joined", uselist=False)

@event.listens_for(Cart, "after_insert")
def set_cart_name(mapper, connection, target: Cart):
    if target.name: return
    cart_name = f"Заказ #{target.id}"
    connection.execute(Cart.__table__.update().where(Cart.id == target.id).values(name=cart_name))
