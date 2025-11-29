from fastapi import APIRouter, HTTPException
from src.helpers import TelegramAuthPayload, verify_telegram_init_data

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/")
async def auth(payload: TelegramAuthPayload):
    """
    Принимает init_data из Telegram WebApp, проверяет подпись,
    возвращает инфу о пользователе.

    Фронт: apiPost("/auth", { init_data: tg.initData })
    """

    data = verify_telegram_init_data(payload.init_data)

    user = data.get("user")
    if not user: raise HTTPException(status_code=400, detail="No user in init data")
    internal_user_id = user["id"]

    result = {
        "user_id": internal_user_id,
        "telegram_user": user,
        "chat_instance": data.get("chat_instance"),
        "chat_type": data.get("chat_type"),
    }

    return result
