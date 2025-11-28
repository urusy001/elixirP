from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from config import MOSCOW_TZ
from src.webapp.models import Giveaway
from src.webapp.schemas.giveaway import GiveawayCreate, GiveawayUpdate


def _update_closed_flag(giveaway: Giveaway) -> None:
    """
    Автоматически выставляет giveaway.closed в зависимости от end_date.
    True, если конец розыгрыша уже наступил по Мск.
    """
    if giveaway.end_date is None:
        giveaway.closed = False
        return

    now_moscow = datetime.now(MOSCOW_TZ)
    giveaway.closed = giveaway.end_date <= now_moscow


async def get_giveaways(db: AsyncSession) -> Optional[list[Giveaway]]:
    result = await db.execute(select(Giveaway))
    giveaways = result.scalars().all()

    # при чтении можно обновлять closed (если хочешь, чтобы флаг всегда был актуален)
    for g in giveaways:
        _update_closed_flag(g)
    await db.commit()  # если не хочешь автосейва — можно убрать

    return giveaways


async def get_giveaway(db: AsyncSession, giveaway_id: int) -> Optional[Giveaway]:
    result = await db.execute(select(Giveaway).where(Giveaway.id == giveaway_id))
    giveaway = result.scalar_one_or_none()
    if giveaway:
        _update_closed_flag(giveaway)
        await db.commit()  # опционально
    return giveaway


async def create_giveaway(db: AsyncSession, data: GiveawayCreate):
    giveaway = Giveaway(**data.model_dump())

    # считаем closed перед сохранением
    _update_closed_flag(giveaway)

    db.add(giveaway)
    await db.commit()
    await db.refresh(giveaway)
    return giveaway


async def update_giveaway(db: AsyncSession, giveaway_id: int, data: GiveawayUpdate):
    giveaway = await get_giveaway(db, giveaway_id)
    if not giveaway:
        return None

    update_data = data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(giveaway, field, value)

    if "closed" not in update_data:
        _update_closed_flag(giveaway)

    await db.commit()
    await db.refresh(giveaway)
    return giveaway


async def delete_giveaway(db: AsyncSession, giveaway_id: int):
    giveaway = await get_giveaway(db, giveaway_id)
    if not giveaway:
        return False
    await db.delete(giveaway)
    await db.commit()
    return True