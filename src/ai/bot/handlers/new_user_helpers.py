from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from src.webapp import get_session
from src.webapp.crud import get_user_total_requests, update_user, upsert_user, get_user
from src.webapp.schemas import UserCreate, UserUpdate
from src.ai.bot.texts import user_texts
from src.ai.bot.keyboards import user_keyboards
from src.ai.bot.states import user_states

PHONE_GATE_BOTS = ("professor", "dose")

async def _request_phone(message: Message, state: FSMContext, full_name: str | None = None):
    await state.set_state(user_states.Registration.phone)
    display_name = full_name or message.from_user.full_name
    return await message.answer(user_texts.verify_phone.replace('*', display_name), reply_markup=user_keyboards.phone)

async def _ensure_user(message: Message, professor_client):
    user_id = message.from_user.id
    async with get_session() as session:
        user = await get_user(session, 'tg_id', user_id)
        if not user:
            thread_id = await professor_client.create_thread()
            user = await upsert_user(session, UserCreate(tg_id=user_id, name=message.from_user.first_name, surname=message.from_user.last_name, thread_id=thread_id))
            return user
        if not user.thread_id:
            thread_id = await professor_client.create_thread()
            user = await update_user(session, user_id, UserUpdate(thread_id=thread_id))

    return user


async def _get_unverified_requests_count(user_id: int) -> int:
    async with get_session() as session: return await get_user_total_requests(session, user_id, PHONE_GATE_BOTS)
