from sqlalchemy import select, update, bindparam, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.helpers import normalize_user_value
from src.webapp.models import User
from src.webapp.schemas import UserCreate, UserUpdate


# ---------------- CREATE ----------------
async def create_user(db: AsyncSession, data: UserCreate) -> User:
    user = User(**data.dict())
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


# ---------------- READ ----------------
async def get_user(db, column_name: str, raw_value: str) -> User | None:
    column = getattr(User, column_name, None)
    if column is None:
        return None

    value = normalize_user_value(column_name, raw_value)
    stmt = select(User).where(column == bindparam("v", value, type_=column.type))
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_tg_refs(db: AsyncSession, value, by: str = 'tg_ref_id') -> User | None:
    if not hasattr(User, by):
        raise AttributeError(f"User model has no attribute '{by}'")

    column = getattr(User, by)
    result = await db.execute(select(User).where(column == value))
    return result.scalars().all()


async def get_users(db: AsyncSession) -> list[User]:
    result = await db.execute(select(User))
    return result.scalars().all()


# ---------------- UPDATE ----------------
async def update_user(db: AsyncSession, tg_id: int, data: UserUpdate) -> User | None:
    user = await db.get(User, tg_id)
    if not user:
        return None

    for field, value in data.dict(exclude_unset=True).items():
        setattr(user, field, value)

    await db.commit()
    await db.refresh(user)
    return user

# ---------------- UPSERT ----------------
async def upsert_user(db: AsyncSession, user_upsert) -> User:
    """
    Upsert-поведение для User:
    - Сначала ищем по tg_id.
    - Если не нашли – ищем по phone.
    - Если не нашли – ищем по email.
    - Если нашли – обновляем поля (кроме тех, что None).
    - Если не нашли – создаём нового.
    """

    # user_upsert — скорее всего Pydantic-модель: берём только выставленные поля
    data = user_upsert.model_dump(exclude_unset=True)

    tg_id: int | None = data.get("tg_id")
    phone: str | None = data.get("phone")
    email: str | None = data.get("email")

    user: User | None = None

    # 1) Пробуем найти по tg_id (это твой primary key)
    if tg_id is not None:
        res = await db.execute(select(User).where(User.tg_id == tg_id))
        user = res.scalar_one_or_none()

    # 2) Если по tg_id нет – пробуем по phone
    if user is None and phone:
        res = await db.execute(select(User).where(User.phone == phone))
        user = res.scalar_one_or_none()

    # 3) Если по phone нет – пробуем по email
    if user is None and email:
        res = await db.execute(select(User).where(User.email == email))
        user = res.scalar_one_or_none()

    if user is not None:
        # 4) Обновляем найденного пользователя
        for field, value in data.items():
            # чтобы не затирать существующие значения на None
            if value is not None:
                setattr(user, field, value)
    else:
        # 5) Создаём нового
        user = User(**data)
        db.add(user)

    try:
        await db.commit()
    except IntegrityError:
        # 6) Обработка гонок/конфликтов UNIQUE (phone/email)
        await db.rollback()

        filters = []
        if tg_id is not None:
            filters.append(User.tg_id == tg_id)
        if phone:
            filters.append(User.phone == phone)
        if email:
            filters.append(User.email == email)

        if not filters:
            # вообще не по чему искать – пробрасываем ошибку выше
            raise

        res = await db.execute(select(User).where(or_(*filters)))
        user = res.scalar_one()

    await db.refresh(user)
    return user

async def increment_tokens(db: AsyncSession, tg_id: int, input_inc: int = 0, output_inc: int = 0):
    stmt = (
        update(User)
        .where(User.tg_id == tg_id)
        .values(
            input_tokens=User.input_tokens + input_inc,
            output_tokens=User.output_tokens + output_inc
        )
        .execution_options(synchronize_session=False)
    )
    await db.execute(stmt)
    await db.commit()


# ---------------- DELETE ----------------
async def delete_user(db: AsyncSession, tg_id: int) -> bool:
    user = await db.get(User, tg_id)
    if not user:
        return False
    await db.delete(user)
    await db.commit()
    return True

async def update_premium_requests(db: AsyncSession, value: int = 2) -> int:
    result = await db.execute(
        update(User)
        .values(premium_requests=value)
        .execution_options(synchronize_session=False)
    )
    await db.commit()
    print(f"Updated {result.rowcount or 0} to add requests with {value}")


async def update_user_name(i, first_name, last_name):
    from src.webapp import get_session
    async with get_session() as _session: await update_user(_session, i, UserUpdate(name=first_name, surname=last_name))
