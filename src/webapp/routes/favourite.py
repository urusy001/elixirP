from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.webapp.crud.favourite import add_favourite, remove_favourite
from src.webapp.database import get_db
from src.webapp.schemas import FavouriteCreate, FavouriteDelete, FavouriteOut

router = APIRouter(
    prefix="/favourites",
    tags=["favourites"],
)


class FavouriteDeleteResponse(BaseModel): success: bool


@router.post("", response_model=FavouriteOut, name="favourites_add")
async def favourite_post(favourite_create: FavouriteCreate, db: AsyncSession = Depends(get_db)):
    """
    Добавить товар в избранное.
    Возвращает объект избранного.
    """
    try: fav = await add_favourite(db, favourite_create)
    except ValueError as exc: raise HTTPException(status_code=404, detail=str(exc))
    return fav


@router.delete("", response_model=FavouriteDeleteResponse, name="favourites_delete")
async def favourite_del(favourite_delete: FavouriteDelete, db: AsyncSession = Depends(get_db)):
    """
    Удалить товар из избранного.
    Возвращает {"success": true/false}.
    """
    success = await remove_favourite(db, favourite_delete)
    return FavouriteDeleteResponse(success=success)