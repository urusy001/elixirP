from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from src.ai.bot.texts import user_texts
from src.ai.bot.keyboards import user_keyboards
from src.ai.bot.states import user_states
from src.ai.webapp_client import webapp_client

PHONE_GATE_BOTS = ("professor", "dose")

async def _request_phone(message: Message, state: FSMContext, full_name: str | None = None):
    await state.set_state(user_states.Registration.phone)
    display_name = full_name or message.from_user.full_name
    return await message.answer(user_texts.verify_phone.replace('*', display_name), reply_markup=user_keyboards.phone)

async def _ensure_user(message: Message, professor_client):
    user_id = message.from_user.id
    user = await webapp_client.get_user("tg_id", user_id)
    if not user:
        thread_id = await professor_client.create_thread()
        user = await webapp_client.upsert_user({"tg_id": user_id, "name": message.from_user.first_name, "surname": message.from_user.last_name, "thread_id": thread_id})
        return user
    if not user.thread_id:
        thread_id = await professor_client.create_thread()
        user = await webapp_client.update_user(user_id, {"thread_id": thread_id})
    return user


async def _get_unverified_requests_count(user_id: int) -> int:
    return await webapp_client.get_user_total_requests(user_id, PHONE_GATE_BOTS)
