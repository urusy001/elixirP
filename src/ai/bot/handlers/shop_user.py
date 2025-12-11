from datetime import datetime
from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile, Message, CallbackQuery

from config import OWNER_TG_IDS, AI_BOT_TOKEN2, AI_BOT_TOKEN, MOSCOW_TZ, DATA_DIR
from src.helpers import CHAT_NOT_BANNED_FILTER
from src.webapp import get_session
from src.webapp.crud import write_usage, increment_tokens, get_user, update_user
from src.webapp.schemas import UserUpdate
from src.ai.bot.texts import user_texts
from src.ai.bot.keyboards import user_keyboards
from src.ai.bot.states import user_states

router = Router(name="shop_user")

@router.message(Command('shop'))
async def app(message: Message): await message.answer(user_texts.offer, reply_markup=user_keyboards.open_app)

@router.message(Command('about'))
async def about(message: Message): await message.answer(user_texts.about)

@router.message(Command('offer'))
async def offer(message: Message): await message.answer_document(FSInputFile(DATA_DIR / 'offer.pdf'), caption=user_texts.offer)

@router.message(CommandStart())
async def handle_user_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    result = await CHAT_NOT_BANNED_FILTER(user_id)
    if not result: return await message.answer(user_texts.banned_in_channel)
    async with get_session() as session: user = await get_user(session, 'tg_id', user_id)
    if not user:
        await state.set_state(user_states.Registration.phone)
        return await message.answer(user_texts.verify_phone.replace('*', message.from_user.full_name), reply_markup=user_keyboards.phone)

    if user.blocked_until and user.blocked_until.replace(tzinfo=MOSCOW_TZ) > datetime.now(MOSCOW_TZ): return await message.answer(user_texts.banned_until.replace("Блокировка до 9999-12-31, п", "П").replace("name", message.from_user.full_name).replace("date", f'{user.blocked_until.date()}'))
    return await message.answer(user_texts.greetings.replace('full_name', message.from_user.full_name), reply_markup=user_keyboards.main_menu)

@router.message(user_states.Registration.phone)
async def handle_user_registration(message: Message, state: FSMContext, professor_bot, professor_client):
    user_id = message.from_user.id
    result = await CHAT_NOT_BANNED_FILTER(user_id)
    if not result: return await message.answer(user_texts.banned_in_channel)
    if not message.contact: return await message.answer(user_texts.verify_phone.replace('*', message.from_user.full_name), reply_markup=user_keyboards.phone)

    phone = message.contact.phone_number
    await state.clear()
    thread_id = await professor_bot.create_user(message.from_user.id, phone)
    response = await professor_client.send_message(f"Я написал первое сообщение. Мое имя в Telegram — {message.from_user.full_name}.", thread_id=thread_id)
    bot_id = str(message.bot.id)
    if bot_id == AI_BOT_TOKEN.split(':')[0]: bot = "professor"
    elif bot_id == AI_BOT_TOKEN2.split(':')[0]: bot = "dose"
    else: bot = "new"

    async with get_session() as session:
        await increment_tokens(session, message.from_user.id, response['input_tokens'], response['output_tokens'])
        await write_usage(session, message.from_user.id, response['input_tokens'], response['output_tokens'], bot=bot)

    await professor_bot.parse_response(response, message)
    return await message.delete()


@router.message(Command('new_chat'))
async def handle_new_chat(message: Message, state: FSMContext, professor_client):
    user_id = message.from_user.id
    result = await CHAT_NOT_BANNED_FILTER(user_id)
    if not result: return await message.answer(user_texts.banned_in_channel)
    thread_id = await professor_client.create_thread()
    async with get_session() as session: await update_user(session, message.from_user.id, UserUpdate(thread_id=thread_id))
    await state.update_data(thread_id=thread_id)
    return await message.answer(user_texts.new_chat)

@router.message(lambda message: message.text)
async def handle_text_message(message: Message, state: FSMContext, professor_bot, professor_client):
    user_id = message.from_user.id
    result = await CHAT_NOT_BANNED_FILTER(user_id)
    if not result: return await message.answer(user_texts.banned_in_channel)

    async with get_session() as session: user = await get_user(session, 'tg_id', user_id)
    if not user: return await handle_user_start(message, state, professor_bot, professor_client)
    if user.blocked_until and user.blocked_until.replace(tzinfo=MOSCOW_TZ) > datetime.now(MOSCOW_TZ): return await message.answer(user_texts.banned_until.replace("Блокировка до 9999-12-31, п", "П").replace("name", message.from_user.full_name).replace("date", f'{user.blocked_until.date()}'))

    response = await professor_client.send_message(message.text, user.thread_id)
    bot_id = str(message.bot.id)
    if bot_id == AI_BOT_TOKEN.split(':')[0]: bot = "professor"
    elif bot_id == AI_BOT_TOKEN2.split(':')[0]: bot = "dose"
    else: bot = "new"

    async with get_session() as session:
        await increment_tokens(session, message.from_user.id, response['input_tokens'], response['output_tokens']),
        await write_usage(session, message.from_user.id, response['input_tokens'], response['output_tokens'], bot=bot)

    return await professor_bot.parse_response(response, message)


@router.callback_query(lambda call: call.from_user.id not in OWNER_TG_IDS and call.data.startswith("user"))
async def handle_user_call(call: CallbackQuery, state: FSMContext):
    data = call.data.removeprefix("user:").split(":")
    state_data = await state.get_data()
    if data[0] == "about": await about(call.message)
    elif data[0] == "offer": await offer(call.message)
    elif data[0] == "ai":
        if data[1] == "start": await call.message.edit_text(user_texts.pick_ai, reply_markup=user_keyboards.pick_ai)
