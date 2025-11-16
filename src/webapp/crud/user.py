from sqlalchemy import select, update, bindparam
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
async def get_user(db, column_name: str, raw_value: str):
    column = getattr(User, column_name, None)
    if column is None:
        return None

    value = normalize_user_value(column_name, raw_value)
    stmt = select(User).where(column == bindparam("v", value, type_=column.type))
    result = await db.execute(stmt)
    return result.scalars().all()


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
async def upsert_user(db: AsyncSession, data: UserCreate) -> User:
    """
    Create or update a user by tg_id.

    - If user with this tg_id exists: update basic profile fields
      (does NOT touch input_tokens/output_tokens unless you explicitly
      put that logic in).
    - If user does not exist: create a new row.
    """
    tg_id = data.tg_id
    user = await db.get(User, tg_id)

    if user is None:
        # create new user
        user = User(**data.dict())
        db.add(user)
    else:
        # update existing user – ignore tg_id and token counters by default
        update_data = data.dict()
        update_data.pop("tg_id", None)

        # don't reset counters on upsert unless you really want that
        update_data.pop("input_tokens", None)
        update_data.pop("output_tokens", None)

        for field, value in update_data.items():
            setattr(user, field, value)

    await db.commit()
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
