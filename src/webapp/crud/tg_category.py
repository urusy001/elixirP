from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.webapp.models.tg_category import TgCategory
from src.webapp.schemas.tg_category import TgCategoryCreate


async def create_tg_category(db: AsyncSession, data: TgCategoryCreate) -> TgCategory:
    obj = TgCategory(name=data.name, description=data.description)
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return obj


async def list_tg_categories(db: AsyncSession, *, limit: int = 200, offset: int = 0) -> list[TgCategory]:
    q = select(TgCategory).order_by(TgCategory.name.asc()).offset(offset).limit(limit)
    res = await db.execute(q)
    return list(res.scalars().all())


async def get_tg_category_by_name(db: AsyncSession, name: str) -> TgCategory | None:
    q = select(TgCategory).where(TgCategory.name.ilike(name.strip()))
    res = await db.execute(q)
    return res.scalars().first()


async def delete_tg_category(db: AsyncSession, category: TgCategory) -> None:
    await db.delete(category)
    await db.commit()