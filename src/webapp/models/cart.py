from sqlalchemy import BigInteger, Column, String, Boolean, DateTime, func, event, ForeignKey
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

    user_id = Column(
        BigInteger,
        ForeignKey("users.tg_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name = Column(
        String,
        nullable=False,
        default="",  # will be overwritten by after_insert
    )

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
    cart_name = f"Корзина #{target.id}"
    connection.execute(
        Cart.__table__
        .update()
        .where(Cart.id == target.id)
        .values(name=cart_name)
    )