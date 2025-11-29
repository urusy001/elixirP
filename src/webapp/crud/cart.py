from datetime import datetime
from typing import Optional, Sequence
from sqlalchemy.orm import Session

from src.webapp.models import Cart


def get_cart(db: Session, cart_id: int) -> Optional[Cart]:
    return db.query(Cart).filter(Cart.id == cart_id).first()


def get_cart_by_tg_id(db: Session, tg_id: int) -> Optional[Cart]:
    """
    Текущая активная корзина пользователя (если логика "одна активная корзина").
    """
    return (
        db.query(Cart)
        .filter(Cart.tg_id == tg_id)
        .order_by(Cart.last_updated.desc())
        .first()
    )


def list_carts_by_tg_id(db: Session, tg_id: int) -> Sequence[Cart]:
    return (
        db.query(Cart)
        .filter(Cart.tg_id == tg_id)
        .order_by(Cart.last_updated.desc())
        .all()
    )


def create_cart(
        db: Session,
        tg_id: int,
        bag_id: Optional[int] = None,
        total: float = 0.0,
        **extra_fields,
) -> Cart:
    """
    Создать новую Cart для пользователя.
    Можно привязать к существующей Bag (bag_id).
    """
    now = datetime.utcnow()
    cart = Cart(
        tg_id=tg_id,
        bag_id=bag_id,
        total=total,
        last_updated=now,
        **extra_fields,
    )
    db.add(cart)
    db.commit()
    db.refresh(cart)
    return cart


def update_cart(db: Session, cart: Cart, **fields) -> Cart:
    """
    Обновить Cart (total, bag_id, status и т.д.).
    last_updated обновляем автоматически.
    """
    for key, value in fields.items():
        setattr(cart, key, value)
    cart.last_updated = datetime.utcnow()
    db.add(cart)
    db.commit()
    db.refresh(cart)
    return cart


def delete_cart(db: Session, cart: Cart) -> None:
    db.delete(cart)
    db.commit()