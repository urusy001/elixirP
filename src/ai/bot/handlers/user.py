import asyncio

from aiogram import Router
from aiogram.enums import ChatType
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from config import PROFESSOR_BOT_TOKEN, OWNER_TG_IDS, BOT_KEYWORDS, PROFESSOR_ASSISTANT_ID, DOSE_ASSISTANT_ID, NEW_ASSISTANT_ID
from src.ai.bot.keyboards import user_keyboards
from src.ai.bot.states import user_states
from src.ai.bot.texts import user_texts
from src.helpers import with_typing, CHAT_NOT_BANNED_FILTER, check_blocked
from src.webapp import get_session
from src.webapp.crud import update_user, increment_tokens, write_usage, get_user, update_user_name, upsert_user, get_user_total_requests
from src.webapp.schemas import UserUpdate, UserCreate
from src.tg_methods import normalize_phone

professor_user_router = Router(name="user")
dose_user_router = Router(name="user3")
UNVERIFIED_REQUEST_LIMIT = 5
PHONE_GATE_BOTS = ("professor", "dose")

professor_user_router.message.filter(lambda message: message.from_user.id not in OWNER_TG_IDS and message.chat.type == ChatType.PRIVATE, check_blocked)
professor_user_router.callback_query.filter(lambda call: call.data.startswith("user") and call.from_user.id not in OWNER_TG_IDS and call.message.chat.type == ChatType.PRIVATE, check_blocked)
dose_user_router.message.filter(lambda message: message.from_user.id not in OWNER_TG_IDS and message.chat.type == ChatType.PRIVATE, check_blocked)
dose_user_router.callback_query.filter(lambda call: call.data.startswith("user") and call.from_user.id not in OWNER_TG_IDS and call.message.chat.type == ChatType.PRIVATE, check_blocked)

def _resolve_assistant_id(message: Message) -> str:
    bot_id = str(message.bot.id)
    if bot_id == PROFESSOR_BOT_TOKEN.split(':')[0]: return PROFESSOR_ASSISTANT_ID
    return DOSE_ASSISTANT_ID

async def _request_phone(message: Message, state: FSMContext):
    await state.set_state(user_states.Registration.phone)
    return await message.answer(user_texts.verify_phone.replace('*', message.from_user.full_name), reply_markup=user_keyboards.phone)

def _should_request_phone(user, assistant_id: str, used_requests: int) -> bool:
    if user and user.tg_phone: return False
    if assistant_id == NEW_ASSISTANT_ID: return True
    return used_requests >= UNVERIFIED_REQUEST_LIMIT

async def _ensure_user(message: Message, professor_client):
    user_id = message.from_user.id
    async with get_session() as session:
        user = await get_user(session, 'tg_id', user_id)
        if not user:
            thread_id = await professor_client.create_thread()
            user = await upsert_user(session, UserCreate(
                tg_id=user_id,
                name=message.from_user.first_name,
                surname=message.from_user.last_name,
                thread_id=thread_id,
            ))
            return user
        if not user.thread_id:
            thread_id = await professor_client.create_thread()
            user = await update_user(session, user_id, UserUpdate(thread_id=thread_id))
    return user


async def _get_unverified_requests_count(user_id: int) -> int:
    async with get_session() as session:
        return await get_user_total_requests(session, user_id, PHONE_GATE_BOTS)


@professor_user_router.message(CommandStart())
@dose_user_router.message(CommandStart())
async def handle_user_start(message: Message, state: FSMContext, professor_bot, professor_client):
    user_id = message.from_user.id
    result = await CHAT_NOT_BANNED_FILTER(message)
    if not result: return await message.answer(user_texts.banned_in_channel)
    user = await _ensure_user(message, professor_client)
    assistant_id = _resolve_assistant_id(message)
    used_requests = 0 if user.tg_phone else await _get_unverified_requests_count(user_id)
    if _should_request_phone(user, assistant_id, used_requests): return await _request_phone(message, state)

    if user.tg_phone: asyncio.create_task(update_user_name(user_id, message.from_user.first_name, message.from_user.last_name))
    response = await professor_client.send_message(f"ОБРАЩАЙСЯ ТОЛЬКО НА ВЫ, Я написал первое сообщение или возобновил наш диалог. Начни/возобнови диалог. Мое имя в Telegram — {message.from_user.full_name}.", user.thread_id, assistant_id)
    async with get_session() as session:
        await increment_tokens(session, message.from_user.id, response['input_tokens'], response['output_tokens'])
        await write_usage(session, message.from_user.id, response['input_tokens'], response['output_tokens'], BOT_KEYWORDS[assistant_id])

    return await professor_bot.parse_response(response, message, back_menu=True)


@professor_user_router.message(user_states.Registration.phone)
@dose_user_router.message(user_states.Registration.phone)
async def handle_user_registration(message: Message, state: FSMContext, professor_bot, professor_client):
    result = await CHAT_NOT_BANNED_FILTER(message)
    if not result: return await message.answer(user_texts.banned_in_channel)
    if not message.contact: return await message.answer(user_texts.verify_phone.replace('*', message.from_user.full_name), reply_markup=user_keyboards.phone)

    phone = message.contact.phone_number
    await state.clear()
    thread_id = await professor_bot.create_user(message.from_user.id, normalize_phone(phone), message.from_user.first_name, message.from_user.last_name)
    assistant_id = _resolve_assistant_id(message)
    response = await professor_client.send_message(f"ОБРАЩАЙСЯ ТОЛЬКО НА ВЫ, Я написал первое сообщение. Мое имя в Telegram — {message.from_user.full_name}.", thread_id, assistant_id)

    async with get_session() as session:
        await increment_tokens(session, message.from_user.id, response['input_tokens'], response['output_tokens'])
        await write_usage(session, message.from_user.id, response['input_tokens'], response['output_tokens'], BOT_KEYWORDS[assistant_id])

    await professor_bot.parse_response(response, message)
    return await message.delete()


@professor_user_router.message(Command('new_chat'))
@dose_user_router.message(Command('new_chat'))
async def handle_new_chat(message: Message, state: FSMContext, professor_client):
    result = await CHAT_NOT_BANNED_FILTER(message)
    if not result: return await message.answer(user_texts.banned_in_channel)
    thread_id = await professor_client.create_thread()
    async with get_session() as session: await update_user(session, message.from_user.id, UserUpdate(thread_id=thread_id))
    await state.update_data(thread_id=thread_id)
    return await message.answer(user_texts.new_chat)

@professor_user_router.message(lambda message: message.text)
@dose_user_router.message(lambda message: message.text)
@with_typing
async def handle_text_message(message: Message, state: FSMContext, professor_bot, professor_client):
    user_id = message.from_user.id
    result = await CHAT_NOT_BANNED_FILTER(message)
    if not result: return await message.answer(user_texts.banned_in_channel)
    user = await _ensure_user(message, professor_client)
    assistant_id = _resolve_assistant_id(message)
    used_requests = 0 if user.tg_phone else await _get_unverified_requests_count(user_id)
    if _should_request_phone(user, assistant_id, used_requests): return await _request_phone(message, state)
    if user.tg_phone: asyncio.create_task(update_user_name(user_id, message.from_user.first_name, message.from_user.last_name))
    response = await professor_client.send_message(message.text, user.thread_id, assistant_id)

    async with get_session() as session:
        await increment_tokens(session, message.from_user.id, response['input_tokens'], response['output_tokens']),
        await write_usage(session, message.from_user.id, response['input_tokens'], response['output_tokens'], BOT_KEYWORDS[assistant_id])

    return await professor_bot.parse_response(response, message, back_menu=True)

@professor_user_router.callback_query()
@dose_user_router.callback_query()
async def handle_call(call: CallbackQuery): await call.message.answer("Напишите сообщение или очистите историю диалога командой /new_chat")
