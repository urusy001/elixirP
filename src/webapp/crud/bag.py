from typing import Optional, Sequence

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.webapp.models.bag import Bag


# === BAG CRUD ===

async def create_bag(
        db: AsyncSession,
        cart_id: int,
        name: str | None = None,
) -> Bag:
    bag = Bag(cart_id=cart_id, name=name)
    db.add(bag)
    await db.flush()
    return bag


async def get_bag_by_id(
        db: AsyncSession,
        bag_id: int,
) -> Optional[Bag]:
    result = await db.execute(
        select(Bag).where(Bag.id == bag_id)
    )
    return result.scalar_one_or_none()


async def get_bags_for_cart(
        db: AsyncSession,
        cart_id: int,
) -> Sequence[Bag]:
    result = await db.execute(
        select(Bag).where(Bag.cart_id == cart_id)
    )
    return result.scalars().all()


async def rename_bag(
        db: AsyncSession,
        bag: Bag,
        new_name: str,
) -> Bag:
    bag.name = new_name
    db.add(bag)
    await db.flush()
    return bag


async def delete_bag(
        db: AsyncSession,
        bag_id: int,
) -> None:
    await db.execute(
        delete(Bag).where(Bag.id == bag_id)
    )
    await db.flush()