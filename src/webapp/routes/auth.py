from fastapi import APIRouter, HTTPException

from src.helpers import TelegramAuthPayload, validate_init_data
from src.webapp import get_session
from src.webapp.crud import upsert_user, get_user_carts
from src.webapp.schemas import UserCreate

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/")
async def auth(payload: TelegramAuthPayload):
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

    async with get_session() as session:
        user = await upsert_user(session, user_upsert)
        carts = await get_user_carts(session, user.tg_id)

    result = {"user": user.to_dict()}
    result["user"].update({"accepted_terms": bool(carts)})
    return result
