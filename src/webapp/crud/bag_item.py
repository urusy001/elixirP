from typing import Optional, Sequence

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.webapp.models.bag_item import BagItem


# === BAG ITEM CRUD ===

async def add_item_to_bag(
        db: AsyncSession,
        bag_id: int,
        product_id: int,
        quantity: int = 1,
) -> BagItem:
    item = BagItem(
        bag_id=bag_id,
        product_id=product_id,
        quantity=quantity,
    )
    db.add(item)
    await db.flush()
    return item


async def get_item_by_id(
        db: AsyncSession,
        item_id: int,
) -> Optional[BagItem]:
    result = await db.execute(
        select(BagItem).where(BagItem.id == item_id)
    )
    return result.scalar_one_or_none()


async def get_items_for_bag(
        db: AsyncSession,
        bag_id: int,
) -> Sequence[BagItem]:
    result = await db.execute(
        select(BagItem).where(BagItem.bag_id == bag_id)
    )
    return result.scalars().all()


async def update_item_quantity(
        db: AsyncSession,
        item: BagItem,
        quantity: int,
) -> BagItem:
    item.quantity = quantity
    db.add(item)
    await db.flush()
    return item


async def remove_item(
        db: AsyncSession,
        item_id: int,
) -> None:
    await db.execute(
        delete(BagItem).where(BagItem.id == item_id)
    )
    await db.flush()