from typing import Optional, Sequence
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.webapp.models import CartItem
from src.webapp.models.cart import Cart
from src.webapp.schemas.cart import CartCreate, CartUpdate


async def get_cart_by_id(db: AsyncSession, cart_id: int) -> Optional[Cart]:
    """Get a single cart by its ID."""
    result = await db.execute(
        select(Cart).where(Cart.id == cart_id)
    )
    return result.scalar_one_or_none()


async def get_user_carts(db: AsyncSession, user_id: int, is_active: Optional[bool] = None) -> Sequence[Cart]:
    """
    List carts for a user.
    - if is_active is None  -> return all carts
    - if is_active is True  -> only unpaid/unprocessed carts
    - if is_active is False -> only closed/processed carts
    """
    query = select(Cart).where(Cart.user_id == user_id)

    if is_active is not None: query = query.where(Cart.is_active.is_(is_active))
    query = query.order_by(Cart.created_at.desc())
    result = await db.execute(query)
    return result.scalars().all()


async def get_active_user_carts(db: AsyncSession, user_id: int) -> Sequence[Cart]:
    """
    Return ALL active (unpaid/unprocessed) carts for this user.
    """
    result = await db.execute(
        select(Cart)
        .where(
            Cart.user_id == user_id,
            Cart.is_active.is_(True),
            )
        .order_by(Cart.created_at.desc())
    )
    return result.scalars().all()


async def create_cart(db: AsyncSession, data: CartCreate) -> Cart:
    """
    Create a new cart.
    is_active in CartCreate decides whether it starts as unpaid/processed.
    """
    cart = Cart(
        user_id=data.user_id,
        is_active=data.is_active,
    )
    db.add(cart)
    await db.commit()
    await db.refresh(cart)
    return cart


async def update_cart(db: AsyncSession, cart: Cart, data: CartUpdate) -> Cart:
    """
    Update cart fields (is_active, name).
    Use this e.g. to mark cart as processed: is_active = False.
    """
    if data.is_active is not None: cart.is_active = data.is_active
    if data.name is not None: cart.name = data.name

    await db.commit()
    await db.refresh(cart)
    return cart


async def delete_cart(db: AsyncSession, cart: Cart) -> None:
    """Delete cart and all its items (cascade)."""
    await db.delete(cart)
    await db.commit()


async def clear_cart(db: AsyncSession, cart_id: int) -> None:
    """
    Delete all items for a given cart.
    """
    await db.execute(
        delete(CartItem).where(CartItem.cart_id == cart_id)
    )
    await db.commit()