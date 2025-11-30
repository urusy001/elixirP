import json

from fastapi import APIRouter, HTTPException

from config import AI_BOT_TOKEN3
from src.helpers import TelegramAuthPayload, verify_telegram_init_data
from src.webapp import get_session
from src.webapp.crud import upsert_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/")
async def auth(payload: TelegramAuthPayload):
    """
    Принимает init_data из Telegram WebApp, проверяет подпись,
    возвращает инфу о пользователе.

    Фронт: apiPost("/auth", { init_data: tg.initData })
    """
    data = verify_telegram_init_data(payload.initData, AI_BOT_TOKEN3)

    tg_user = data.get("user")
    print(json.dumps(tg_user, ensure_ascii=False, indent=4))
    async with get_session() as session: user = await upsert_user(session, )
    if not tg_user: raise HTTPException(status_code=400, detail="No user in init data")
    internal_user_id = user["id"]

    result = {
        "user_id": internal_user_id,
        "telegram_user": user,
        "chat_instance": data.get("chat_instance"),
        "chat_type": data.get("chat_type"),
    }

    return result
