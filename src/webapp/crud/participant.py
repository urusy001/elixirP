from typing import Optional, Sequence, Dict, Any

from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError  # ✅ add this
from sqlalchemy.ext.asyncio import AsyncSession

from src.webapp.models.participant import Participant
from src.webapp.schemas.participant import ParticipantCreate, ParticipantUpdate


async def get_participants(db: AsyncSession, giveaway_id: int) -> list[Participant]:
    stmt = select(Participant).where(Participant.giveaway_id == giveaway_id)
    result = await db.execute(stmt)
    return result.scalars().all()


async def get_participant(db: AsyncSession, giveaway_id: int, tg_id: int) -> Optional[Participant]:
    stmt = (
        select(Participant)
        .where(Participant.giveaway_id == giveaway_id)
        .where(Participant.tg_id == tg_id)
    )
    res = await db.execute(stmt)
    return res.scalar_one_or_none()

async def get_participant_no_giveaway(db: AsyncSession, tg_id: int) -> Optional[Participant]:
    stmt = (
        select(Participant)
        .where(Participant.tg_id == tg_id)
    )
    res = await db.execute(stmt)
    return res.scalar_one_or_none()


async def save_participant_review(
        db: AsyncSession,
        *,
        giveaway_id: int,
        tg_id: int,
        review: Dict[str, Any],
        mark_completed: bool = True,
) -> Optional[Participant]:
    """
    Persist review details to participant and (optionally) set completed_review=True.
    Expected review keys: id, email, phone, fullname (your payload has these).
    """
    p = await get_participant(db, giveaway_id, tg_id)
    if not p:
        return None

    p.review_id = review.get("id")
    p.review_email = review.get("email")
    p.review_phone = review.get("phone")
    p.review_fullname = review.get("fullname")

    if mark_completed:
        p.completed_review = True

    await db.commit()
    await db.refresh(p)
    return p


async def create_participant(db: AsyncSession, data: ParticipantCreate):
    """Idempotent create: if row exists, return it instead of raising."""
    participant = Participant(**data.dict())
    db.add(participant)
    try:
        await db.commit()
        await db.refresh(participant)
        return participant
    except IntegrityError:
        # duplicate (giveaway_id, tg_id) — rollback and fetch existing
        await db.rollback()
        existing = await get_participant(db, data.giveaway_id, data.tg_id)
        if existing is None:
            # extremely rare race — re-raise if truly not found
            raise
        return existing


async def update_participant(db: AsyncSession, giveaway_id: int, tg_id: int, data: ParticipantUpdate):
    participant = await get_participant(db, giveaway_id, tg_id)
    if not participant:
        return None

    update_data = data.dict(exclude_unset=True)
    for field, value in update_data.items():
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


async def get_refs_for_participant(
        db: AsyncSession,
        giveaway_id: int,
        referrer_tg_id: int,
        *,
        completed_subscription: Optional[bool] = None,
        completed_refs: Optional[bool] = None,
        completed_deal: Optional[bool] = None,
        completed_review: Optional[bool] = None,
        limit: Optional[int] = None,
        offset: int = 0,
) -> Sequence[Participant]:
    """
    Return all participants who were referred by `referrer_tg_id` in this giveaway
    (i.e., participants with ref_id == referrer_tg_id).
    Optional boolean filters allow narrowing by completion flags.
    """
    conds = [
        Participant.giveaway_id == giveaway_id,
        Participant.ref_id == referrer_tg_id,
    ]
    if completed_subscription is not None:
        conds.append(Participant.completed_subscription == completed_subscription)
    if completed_refs is not None:
        conds.append(Participant.completed_refs == completed_refs)
    if completed_deal is not None:
        conds.append(Participant.completed_deal == completed_deal)
    if completed_review is not None:
        conds.append(Participant.completed_review == completed_review)

    stmt = select(Participant).where(*conds).order_by(Participant.tg_id.asc())

    if offset:
        stmt = stmt.offset(offset)
    if limit:
        stmt = stmt.limit(limit)

    res = await db.execute(stmt)
    return res.scalars().all()


async def count_refs_for_participant(
        db: AsyncSession,
        giveaway_id: int,
        referrer_tg_id: int,
        *,
        completed_subscription: Optional[bool] = None,
        completed_refs: Optional[bool] = None,
        completed_deal: Optional[bool] = None,
        completed_review: Optional[bool] = None,
) -> int:
    """
    Count referrals for `referrer_tg_id` with the same optional filters as above.
    Useful for eligibility checks (e.g., needs ≥ 3 completed refs).
    """
    conds = [
        Participant.giveaway_id == giveaway_id,
        Participant.ref_id == referrer_tg_id,
    ]
    if completed_subscription is not None:
        conds.append(Participant.completed_subscription == completed_subscription)
    if completed_refs is not None:
        conds.append(Participant.completed_refs == completed_refs)
    if completed_deal is not None:
        conds.append(Participant.completed_deal == completed_deal)
    if completed_review is not None:
        conds.append(Participant.completed_review == completed_review)

    stmt = select(func.count()).select_from(Participant).where(*conds)
    res = await db.execute(stmt)
    return int(res.scalar() or 0)
