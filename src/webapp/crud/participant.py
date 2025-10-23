from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from src.webapp.models import Participant
from src.webapp.schemas.participant import ParticipantCreate, ParticipantUpdate


async def get_participants(db: AsyncSession, giveaway_id: int):
    result = await db.execute(select(Participant).where(Participant.giveaway_id == giveaway_id))
    return result.scalars().all()


async def get_participant(db: AsyncSession, giveaway_id: int, tg_id: int):
    result = await db.execute(
        select(Participant)
        .where(Participant.giveaway_id == giveaway_id)
        .where(Participant.tg_id == tg_id)
    )
    return result.scalar_one_or_none()


async def create_participant(db: AsyncSession, data: ParticipantCreate):
    participant = Participant(**data.dict())
    db.add(participant)
    await db.commit()
    await db.refresh(participant)
    return participant


async def update_participant(db: AsyncSession, giveaway_id: int, tg_id: int, data: ParticipantUpdate):
    participant = await get_participant(db, giveaway_id, tg_id)
    if not participant:
        return None
    for field, value in data.dict(exclude_unset=True).items():
        setattr(participant, field, value)
    await db.commit()
    await db.refresh(participant)
    return participant


async def delete_participant(db: AsyncSession, giveaway_id: int, tg_id: int):
    participant = await get_participant(db, giveaway_id, tg_id)
    if not participant:
        return False
    await db.delete(participant)
    await db.commit()
    return True