from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from src.webapp.models import Giveaway
from src.webapp.schemas.giveaway import GiveawayCreate, GiveawayUpdate


async def get_giveaways(db: AsyncSession) -> list[Giveaway] | None:
    result = await db.execute(select(Giveaway))
    return result.scalars().all()


async def get_giveaway(db: AsyncSession, giveaway_id: int) -> Giveaway | None:
    result = await db.execute(select(Giveaway).where(Giveaway.id == giveaway_id))
    return result.scalar_one_or_none()


async def create_giveaway(db: AsyncSession, data: GiveawayCreate):
    giveaway = Giveaway(**data.model_dump())
    db.add(giveaway)
    await db.commit()
    await db.refresh(giveaway)
    return giveaway


async def update_giveaway(db: AsyncSession, giveaway_id: int, data: GiveawayUpdate):
    giveaway = await get_giveaway(db, giveaway_id)
    if not giveaway:
        return None
    for field, value in data.dict(exclude_unset=True).items():
        setattr(giveaway, field, value)
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