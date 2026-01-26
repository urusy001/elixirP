from typing import Optional, Sequence
from sqlalchemy import select, delete, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload
from datetime import datetime, timezone, timedelta

from config import MOSCOW_TZ
from src.webapp.models import CartItem, Product
from src.webapp.models.cart import Cart
from src.webapp.schemas.cart import CartCreate, CartUpdate


async def get_cart_by_id(db: AsyncSession, cart_id: int) -> Optional[Cart]:
    result = await db.execute(select(Cart).where(Cart.id == cart_id))
    return result.scalar_one_or_none()

async def get_carts(db: AsyncSession, exclude_starting: bool = True) -> Optional[list[Cart]]:
    """Get a single cart by its ID."""
    result = await db.execute(select(Cart))
    carts: list[Cart] = result.scalars().all()
    return [cart for cart in carts if "ачальная" not in cart.name] if exclude_starting else carts


async def get_carts_by_date(db: AsyncSession, dt: datetime) -> list[Cart]:
    dt_msk = dt if dt.tzinfo else dt.replace(tzinfo=MOSCOW_TZ)

    day_start_msk = dt_msk.astimezone(MOSCOW_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    day_end_msk = day_start_msk + timedelta(days=1)

    day_start_utc = day_start_msk.astimezone(timezone.utc)
    day_end_utc = day_end_msk.astimezone(timezone.utc)

    stmt = (
        select(Cart)
        .where(Cart.created_at >= day_start_utc)
        .where(Cart.created_at < day_end_utc)
        .order_by(Cart.created_at.desc())
    )

    carts = (await db.execute(stmt)).scalars().all()
    return [c for c in carts if "ачальная" not in (c.name or "")]

async def get_user_carts(db: AsyncSession, user_id: int, is_active: Optional[bool] = None, exclude_starting: bool = True) -> Sequence[Cart]:
    """
    List carts for a user.
    - if is_active is None  -> return all carts
    - if is_active is True  -> only unpaid/unprocessed carts
    - if is_active is False -> only closed/processed carts
    """
    query = select(Cart).where(Cart.user_id == user_id).options(
        # items + their product + categories
        selectinload(Cart.items)
        .selectinload(CartItem.product)
        .selectinload(Product.tg_categories),

        # items + their feature (variation/dosage)
        selectinload(Cart.items).selectinload(CartItem.feature),

        # promo (you set lazy="joined" but we make it explicit)
        joinedload(Cart.promo),

        # user (for fallback contact info etc.)
        selectinload(Cart.user),
    )

    if is_active is not None: query = query.where(Cart.is_active.is_(is_active))
    query = query.order_by(Cart.created_at.desc())
    result = await db.execute(query)
    carts: list[Cart] = result.scalars().all()
    return [cart for cart in carts if "ачальная" not in cart.name] if exclude_starting else carts

async def create_cart(db: AsyncSession, data: CartCreate) -> Cart:
    """
    Create a new cart.
    is_active in CartCreate decides whether it starts as unpaid/processed.
    """
    cart = Cart(**data.model_dump())
    db.add(cart)
    await db.commit()
    await db.refresh(cart)
    return cart


async def update_cart(db: AsyncSession, cart_id: int, payload: CartUpdate) -> Cart:
    res = await db.execute(select(Cart).where(Cart.id == cart_id))
    cart = res.scalar_one_or_none()
    if cart is None:
        raise ValueError(f"Cart {cart_id} not found")

    patch = payload.model_dump(exclude_unset=True, exclude_none=True)

    for k, v in patch.items():
        setattr(cart, k, v)

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

async def get_user_carts_webapp(
        db: AsyncSession,
        user_id: int,
        is_active: Optional[bool] = None,
        exclude_starting: bool = True,
) -> Sequence[Cart]:
    stmt = (
        select(Cart)
        .where(Cart.user_id == user_id)
        .options(
            # items + product + tg_categories
            selectinload(Cart.items)
            .selectinload(CartItem.product)
            .selectinload(Product.tg_categories),

            # items + feature
            selectinload(Cart.items).selectinload(CartItem.feature),

            # если нужно (не обязательно)
            joinedload(Cart.promo),
            )
        .order_by(Cart.created_at.desc())
    )

    if is_active is not None:
        stmt = stmt.where(Cart.is_active.is_(is_active))

    if exclude_starting:
        # ✅ SQL-фильтр вместо "ачальная" not in Cart.name
        stmt = stmt.where(or_(Cart.name.is_(None), ~Cart.name.ilike("%ачальная%")))

    res = await db.execute(stmt)
    return res.scalars().unique().all()
