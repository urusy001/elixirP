
import random

from sqlalchemy import BigInteger, Column, String, Boolean, DateTime, func, event, ForeignKey, Numeric
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
        default=lambda: random.randint(10 ** 6, 10 ** 7 - 1),
    )

    user_id = Column(
        BigInteger,
        ForeignKey("users.tg_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name = Column(
        String,
        nullable=True,
    )

    sum = Column(Numeric(8, 2), nullable=False, default=0)
    delivery_sum = Column(Numeric(8, 2), nullable=False, default=0)
    delivery_string = Column(String, nullable=False, default="Не указан", server_default="Не указан")
    commentary = Column(String, nullable=True)

    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        index=True,
    )

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

    user = relationship(
        "User",
        back_populates="carts",
    )

    items = relationship(
        "CartItem",
        back_populates="cart",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


@event.listens_for(Cart, "after_insert")
def set_cart_name(mapper, connection, target: Cart):
    cart_name = f"Заказ #{target.id}"
    connection.execute(
        Cart.__table__
        .update()
        .where(Cart.id == target.id)
        .values(name=cart_name)
    )