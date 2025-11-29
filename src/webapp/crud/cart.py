from typing import Optional, Sequence

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.webapp.models.cart import Cart
from src.webapp.models.bag import Bag
from src.webapp.models.bag_item import BagItem


# === CART CRUD ===

async def get_cart_by_id(
        db: AsyncSession,
        cart_id: int,
) -> Optional[Cart]:
    result = await db.execute(
        select(Cart).where(Cart.id == cart_id)
    )
    return result.scalar_one_or_none()


async def get_user_carts(
        db: AsyncSession,
        tg_id: int,
) -> Sequence[Cart]:
    result = await db.execute(
        select(Cart).where(Cart.tg_id == tg_id)
    )
    return result.scalars().all()


async def get_or_create_cart_for_user(
        db: AsyncSession,
        tg_id: int,
) -> Cart:
    result = await db.execute(
        select(Cart).where(Cart.tg_id == tg_id)
    )
    cart = result.scalar_one_or_none()

    if cart is None:
        cart = Cart(tg_id=tg_id)
        db.add(cart)
        await db.flush()  # to get cart.id

    return cart


async def update_cart_total(
        db: AsyncSession,
        cart: Cart,
        new_total,
) -> Cart:
    cart.total = new_total
    db.add(cart)
    await db.flush()
    return cart


async def delete_cart(
        db: AsyncSession,
        cart_id: int,
) -> None:
    await db.execute(
        delete(Cart).where(Cart.id == cart_id)
    )
    await db.flush()