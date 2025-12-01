from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.webapp.models.favourite import Favourite
from src.webapp.models.product import Product
from src.webapp.schemas.favourite import (
    FavouriteBase,
    FavouriteCreate,
    FavouriteDelete,
)


async def get_user_favourites(db: AsyncSession, user_id: int) -> List[Favourite]:
    """
    Вернуть все избранные товары пользователя по user_id.
    """
    result = await db.execute(
        select(Favourite).where(Favourite.user_id == user_id)
    )
    return list(result.scalars().all())


async def get_user_favourite_by_onec(
        db: AsyncSession,
        fav_in: FavouriteBase,
) -> Optional[Favourite]:
    """
    Найти конкретный избранный товар по user_id + onec_id.
    """
    result = await db.execute(
        select(Favourite).where(
            Favourite.user_id == fav_in.user_id,
            Favourite.onec_id == fav_in.onec_id,
            )
    )
    return result.scalars().first()


async def add_favourite(
        db: AsyncSession,
        fav_in: FavouriteCreate,
) -> Favourite:
    """
    Добавить товар в избранное.

    Делает операцию идемпотентной:
    - если уже есть в избранном → просто возвращает существующую запись.
    """
    existing = await get_user_favourite_by_onec(db, fav_in)
    if existing:
        return existing

    # опционально: можно проверить, что такой товар вообще существует
    product_result = await db.execute(
        select(Product).where(Product.onec_id == fav_in.onec_id)
    )
    product_exists = product_result.scalars().first()
    if not product_exists:
        # либо кидаем исключение выше, либо даём 404 на уровне ручки
        raise ValueError(f"Product with onec_id={fav_in.onec_id} not found")

    fav = Favourite(
        user_id=fav_in.user_id,
        onec_id=fav_in.onec_id,
    )
    db.add(fav)
    await db.commit()
    await db.refresh(fav)
    return fav


async def remove_favourite(
        db: AsyncSession,
        fav_in: FavouriteDelete,
) -> bool:
    """
    Удалить товар из избранного.
    Возвращает True, если что-то удалили, False — если записи не было.
    """
    fav = await get_user_favourite_by_onec(db, fav_in)
    if not fav:
        return False

    await db.delete(fav)
    await db.commit()
    return True


async def is_favourite(
        db: AsyncSession,
        fav_in: FavouriteBase,
) -> bool:
    """
    Проверить, находится ли товар в избранном у пользователя.
    """
    result = await db.execute(
        select(Favourite).where(
            Favourite.user_id == fav_in.user_id,
            Favourite.onec_id == fav_in.onec_id,
            )
    )
    return result.scalars().first() is not None