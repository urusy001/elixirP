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
    try:
        user = data.get("user")
        user_upsert = UserCreate(
            tg_id=user["id"],
            name=user["first_name"],
            surname=user["last_name"],
            photo_url=user["photo_url"],
        )
        user = await upsert_user(db, user_upsert)
        carts = await get_user_carts(db, user.tg_id)
        favourites = await get_user_favourites(db, user.tg_id)

        user_dict = user.to_dict()

        user_dict["accepted_terms"] = bool(carts)
        user_dict["favourites"] = [fav.onec_id for fav in favourites]
        print(json.dumps(user_dict, indent=4, ensure_ascii=False))

        return {"user": user_dict}
    except Exception as e:
        return {"user": {
            "tg_id": 7994732323,
            "tg_ref_id": None,
            "tg_phone": "17632730385",
            "photo_url": "https://t.me/i/userpic/320/gW9aIsQa-lmpXo6P0sNmiHj_muG-QRt7nsyi9849Pz9BS3gBjXHb9PxiAlH7IdUj.svg",
            "name": "Paylak",
            "surname": "Urusyan",
            "email": None,
            "phone": None,
            "premium_requests": 793215,
            "thread_id": "thread_jM2U5iNJ71OJo8jyQijnwPOt",
            "input_tokens": 1686106,
            "output_tokens": 52017,
            "blocked_until": None,
            "accepted_terms": True,
            "favourites": [],
        }}
