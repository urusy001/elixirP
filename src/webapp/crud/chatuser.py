from datetime import datetime
from typing import Optional, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import MOSCOW_TZ
from src.webapp.models import ChatUser
from src.webapp.schemas import ChatUserCreate, ChatUserUpdate


async def get_chat_user(db: AsyncSession, user_id: int) -> Optional[ChatUser]:
    result = await db.execute(select(ChatUser).where(ChatUser.id == user_id))
    return result.scalars().first()


async def get_chat_users(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[ChatUser]:
    result = await db.execute(
        select(ChatUser)
        .order_by(ChatUser.id)
        .offset(skip)
        .limit(limit)
    )
    return list(result.scalars().all())


async def create_chat_user(db: AsyncSession, user_in: ChatUserCreate) -> ChatUser:
    db_user = ChatUser(
        id=user_in.id,
        full_name=user_in.full_name,
        username=user_in.username,
        passed_poll=user_in.passed_poll,
        whitelist=user_in.whitelist,
        muted_until=user_in.muted_until,
        times_muted=user_in.times_muted,
        banned_until=user_in.banned_until,
        times_banned=user_in.times_banned,
        messages_sent=user_in.messages_sent,
        times_reported=user_in.times_reported,
        accused_spam=user_in.accused_spam,
        last_accused_text=user_in.last_accused_text,
        poll_attempts=user_in.poll_attempts,
        poll_active=user_in.poll_active,
        poll_message_id=user_in.poll_message_id,
        poll_chat_id=user_in.poll_chat_id,
        poll_id=user_in.poll_id,
        poll_correct_option_id=user_in.poll_correct_option_id,
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user


async def update_chat_user(db: AsyncSession, db_user: ChatUser, user_in: ChatUserUpdate) -> ChatUser:
    data = user_in.dict(exclude_unset=True)
    for field, value in data.items():
        setattr(db_user, field, value)
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user


async def upsert_chat_user(db: AsyncSession, user_in: ChatUserCreate) -> ChatUser:
    db_user = await get_chat_user(db, user_in.id)
    if db_user is None:
        return await create_chat_user(db, user_in)
    update_data = ChatUserUpdate(**user_in.dict(exclude={"id"}))
    return await update_chat_user(db, db_user, update_data)


async def delete_chat_user(db: AsyncSession, user_id: int) -> bool:
    db_user = await get_chat_user(db, user_id)
    if db_user is None:
        return False
    await db.delete(db_user)
    await db.commit()
    return True


async def set_whitelist(db: AsyncSession, user_id: int, value: bool = True) -> Optional[ChatUser]:
    db_user = await get_chat_user(db, user_id)
    if db_user is None:
        return None
    db_user.whitelist = value
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user


async def set_passed_poll(db: AsyncSession, user_id: int, value: bool = True) -> Optional[ChatUser]:
    db_user = await get_chat_user(db, user_id)
    if db_user is None:
        return None
    db_user.passed_poll = value
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user


async def set_muted_until(
        db: AsyncSession,
        user_id: int,
        muted_until: Optional[datetime],
) -> Optional[ChatUser]:
    db_user = await get_chat_user(db, user_id)
    if db_user is None:
        return None
    db_user.muted_until = muted_until
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user


async def set_banned_until(
        db: AsyncSession,
        user_id: int,
        banned_until: Optional[datetime],
) -> Optional[ChatUser]:
    db_user = await get_chat_user(db, user_id)
    if db_user is None:
        return None
    db_user.banned_until = banned_until
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user


async def increment_messages_sent(
        db: AsyncSession,
        user_id: int,
        delta: int = 1,
) -> Optional[ChatUser]:
    db_user = await get_chat_user(db, user_id)
    if db_user is None:
        return None
    db_user.messages_sent = (db_user.messages_sent or 0) + delta
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user


async def increment_times_reported(
        db: AsyncSession,
        user_id: int,
        delta: int = 1,
        accused_spam: Optional[bool] = None,
) -> Optional[ChatUser]:
    db_user = await get_chat_user(db, user_id)
    if db_user is None:
        return None

    db_user.times_reported = (db_user.times_reported or 0) + delta

    if accused_spam is not None:
        db_user.accused_spam = accused_spam

    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user


async def increment_times_muted(
        db: AsyncSession,
        user_id: int,
        delta: int = 1,
) -> Optional[ChatUser]:
    db_user = await get_chat_user(db, user_id)
    if db_user is None:
        return None
    db_user.times_muted = (db_user.times_muted or 0) + delta
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user


async def increment_times_banned(
        db: AsyncSession,
        user_id: int,
        delta: int = 1,
) -> Optional[ChatUser]:
    db_user = await get_chat_user(db, user_id)
    if db_user is None:
        return None
    db_user.times_banned = (db_user.times_banned or 0) + delta
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user


async def get_users_with_active_mute(
        session: AsyncSession,
        now: Optional[datetime] = None,
) -> List[ChatUser]:
    if now is None:
        now = datetime.now(tz=MOSCOW_TZ)
    result = await session.execute(
        select(ChatUser).where(
            ChatUser.muted_until.is_not(None),
            ChatUser.muted_until > now,
            )
    )
    return list(result.scalars().all())