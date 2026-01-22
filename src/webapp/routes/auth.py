import json

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.helpers import TelegramAuthPayload, validate_init_data
from src.webapp import get_session
from src.webapp.crud import upsert_user, get_user_carts, get_user_favourites
from src.webapp.database import get_db
from src.webapp.schemas import UserCreate

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/")
async def auth(payload: TelegramAuthPayload, db: AsyncSession = Depends(get_db)):
    """
    Принимает init_data из Telegram WebApp, проверяет подпись,
    возвращает инфу о пользователе.

    Фронт: apiPost("/auth", { init_data: tg.initData })
    """
    data = validate_init_data(payload.initData)
    user = data.get("user")
    user_upsert = UserCreate(
        tg_id=user["id"],
        name=user["first_name"],
        surname=user["last_name"],
        photo_url=user["photo_url"],
    )
    user = await upsert_user(db, user_upsert)
    carts = await get_user_carts(db, user.tg_id, exclude_starting=False)
    favourites = await get_user_favourites(db, user.tg_id)

    user_dict = user.to_dict()

    user_dict["accepted_terms"] = bool(carts)
    user_dict["favourites"] = [fav.onec_id for fav in favourites]


    return {"user": user_dict}
