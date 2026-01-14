from datetime import datetime
from aiogram import Router
from aiogram.enums import ChatType
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from config import PROFESSOR_BOT_TOKEN, MOSCOW_TZ, OWNER_TG_IDS, BOT_KEYWORDS, PROFESSOR_ASSISTANT_ID, DOSE_ASSISTANT_ID
from src.ai.bot.keyboards import user_keyboards
from src.ai.bot.states import user_states
from src.ai.bot.texts import user_texts
from src.helpers import with_typing, CHAT_NOT_BANNED_FILTER, check_blocked
from src.webapp import get_session
from src.webapp.crud import update_user, increment_tokens, write_usage, get_user
from src.webapp.schemas import UserUpdate

professor_user_router = Router(name="user")
dose_user_router = Router(name="user3")

professor_user_router.message.filter(lambda message: message.from_user.id not in OWNER_TG_IDS and message.chat.type == ChatType.PRIVATE, check_blocked)
professor_user_router.callback_query.filter(lambda call: call.data.startswith("user") and call.from_user.id not in OWNER_TG_IDS and call.message.chat.type == ChatType.PRIVATE, check_blocked)
dose_user_router.message.filter(lambda message: message.from_user.id not in OWNER_TG_IDS and message.chat.type == ChatType.PRIVATE, check_blocked)
dose_user_router.callback_query.filter(lambda call: call.data.startswith("user") and call.from_user.id not in OWNER_TG_IDS and call.message.chat.type == ChatType.PRIVATE, check_blocked)


@professor_user_router.message(CommandStart())
@dose_user_router.message(CommandStart())
async def handle_user_start(message: Message, state: FSMContext, professor_bot, professor_client):
    user_id = message.from_user.id
    result = await CHAT_NOT_BANNED_FILTER(user_id)
    if not result: return await message.answer(user_texts.banned_in_channel)
    async with get_session() as session: user = await get_user(session, 'tg_id', user_id)
    if not user:
        await state.set_state(user_states.Registration.phone)
        return await message.answer(user_texts.verify_phone.replace('*', message.from_user.full_name), reply_markup=user_keyboards.phone)

    if user.blocked_until and user.blocked_until.replace(tzinfo=MOSCOW_TZ) > datetime.now(MOSCOW_TZ): return await message.answer(user_texts.banned_until.replace("Блокировка до 9999-12-31, п", "П").replace("name", message.from_user.full_name).replace("date", f'{user.blocked_until.date()}'))
    if not user.thread_id:
        thread_id = await professor_client.create_thread()
        async with get_session() as session: await update_user(session, user_id, UserUpdate(thread_id=thread_id))

    bot_id = str(message.bot.id)
    if bot_id == PROFESSOR_BOT_TOKEN.split(':')[0]: assistant_id = PROFESSOR_ASSISTANT_ID
    else: assistant_id = DOSE_ASSISTANT_ID
    response = await professor_client.send_message(f"Я написал первое сообщение или возобновил наш диалог. Начни/возобнови диалог. Мое имя в Telegram — {message.from_user.full_name}.", user.thread_id, assistant_id)
    async with get_session() as session:
        await increment_tokens(session, message.from_user.id, response['input_tokens'], response['output_tokens'])
        await write_usage(session, message.from_user.id, response['input_tokens'], response['output_tokens'], BOT_KEYWORDS[assistant_id])

    return await professor_bot.parse_response(response, message, back_menu=True)


@professor_user_router.message(user_states.Registration.phone)
@dose_user_router.message(user_states.Registration.phone)
async def handle_user_registration(message: Message, state: FSMContext, professor_bot, professor_client):
    user_id = message.from_user.id
    result = await CHAT_NOT_BANNED_FILTER(user_id)
    if not result: return await message.answer(user_texts.banned_in_channel)
    if not message.contact: return await message.answer(user_texts.verify_phone.replace('*', message.from_user.full_name), reply_markup=user_keyboards.phone)

    phone = message.contact.phone_number
    await state.clear()
    thread_id = await professor_bot.create_user(message.from_user.id, phone)
    bot_id = str(message.bot.id)
    if bot_id == PROFESSOR_BOT_TOKEN.split(':')[0]: assistant_id = PROFESSOR_ASSISTANT_ID
    else: assistant_id = DOSE_ASSISTANT_ID
    response = await professor_client.send_message(f"Я написал первое сообщение. Мое имя в Telegram — {message.from_user.full_name}.", thread_id, assistant_id)

    async with get_session() as session:
        await increment_tokens(session, message.from_user.id, response['input_tokens'], response['output_tokens'])
        await write_usage(session, message.from_user.id, response['input_tokens'], response['output_tokens'], BOT_KEYWORDS[assistant_id])

    await professor_bot.parse_response(response, message)
    return await message.delete()


@professor_user_router.message(Command('new_chat'))
@dose_user_router.message(Command('new_chat'))
async def handle_new_chat(message: Message, state: FSMContext, professor_client):
    user_id = message.from_user.id
    result = await CHAT_NOT_BANNED_FILTER(user_id)
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
    result = await CHAT_NOT_BANNED_FILTER(user_id)
    if not result: return await message.answer(user_texts.banned_in_channel)
    async with get_session() as session: user = await get_user(session, 'tg_id', user_id)
    if not user: return await handle_user_start(message, state, professor_bot, professor_client)
    if user.blocked_until and user.blocked_until.replace(tzinfo=MOSCOW_TZ) > datetime.now(MOSCOW_TZ): return await message.answer(user_texts.banned_until.replace("Блокировка до 9999-12-31, п", "П").replace("name", message.from_user.full_name).replace("date", f'{user.blocked_until.date()}'))
    bot_id = str(message.bot.id)
    if bot_id == PROFESSOR_BOT_TOKEN.split(':')[0]: assistant_id = PROFESSOR_ASSISTANT_ID
    else: assistant_id = DOSE_ASSISTANT_ID
    print(assistant_id, assistant_id, assistant_id, assistant_id, assistant_id, assistant_id)
    response = await professor_client.send_message(message.text, user.thread_id, assistant_id)

    async with get_session() as session:
        await increment_tokens(session, message.from_user.id, response['input_tokens'], response['output_tokens']),
        await write_usage(session, message.from_user.id, response['input_tokens'], response['output_tokens'], BOT_KEYWORDS[assistant_id])

    return await professor_bot.parse_response(response, message, back_menu=True)

@professor_user_router.callback_query()
@dose_user_router.callback_query()
async def handle_call(call: CallbackQuery): await call.message.answer("Напишите сообщение или очистите историю диалога командой /new_chat")
