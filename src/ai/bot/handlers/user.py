from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.filters import CommandStart, Command

from src.helpers import with_typing
from src.ai.bot.states import user_states
from src.ai.bot.keyboards import user_keyboards
from src.webapp.crud import update_user, increment_tokens, write_usage
from src.webapp.schemas import UserUpdate
from src.webapp import get_session
from config import ADMIN_TG_IDS, AI_BOT_TOKEN, AI_BOT_TOKEN2


router = Router(name="user")
router2 = Router(name="user2")
router3 = Router(name="user3")


@router.message(CommandStart(), lambda message: message.from_user.id not in ADMIN_TG_IDS)
@router2.message(CommandStart(), lambda message: message.from_user.id not in ADMIN_TG_IDS)
@router3.message(CommandStart(), lambda message: message.from_user.id not in ADMIN_TG_IDS)
@with_typing
async def handle_user_start(message: Message, state: FSMContext, professor_bot, professor_client):
    user_id = message.from_user.id
    if user_id not in professor_bot.users:
        await state.set_state(user_states.Registration.phone)
        return await message.answer(
            f"Уважаемый {message.from_user.full_name}, для подтверждения, что вы не робот, нажмите кнопку ниже ⬇️",
            reply_markup=user_keyboards.phone,
        )

    user_data = professor_bot.users[user_id]
    thread_id = user_data.get("thread_id")
    blocked_until = user_data.get("blocked_until")

    if blocked_until and blocked_until > datetime.now(ZoneInfo("Europe/Moscow")):
        return await message.answer(
            f"Уважаемый {message.from_user.full_name}, вы *ЗАБЛОКИРОВАНЫ* за недобросовестное использование нашего продукта.\n\n"
            f"Блокировка до {blocked_until.date()}, при вопросах напишите в поддержку: @paylakurusyan",
            parse_mode="Markdown",
        )

    if not thread_id:
        thread_id = await professor_client.create_thread()
        async with get_session() as session: await update_user(session, user_id, UserUpdate(thread_id=thread_id))
        professor_bot.users[user_id]["thread_id"] = thread_id

    response = await professor_client.send_message(
        f"Я написал первое сообщение или возобновил наш диалог. Начни/возобнови диалог. "
        f"Мое имя в Telegram — {message.from_user.full_name}.",
        thread_id=thread_id,
    )
    async with get_session() as session:
        await increment_tokens(session, message.from_user.id, response['input_tokens'], response['output_tokens'])

        bot_id = str(message.bot.id)
        if bot_id == AI_BOT_TOKEN.split(':')[0]: bot = "professor"
        elif bot_id == AI_BOT_TOKEN2.split(':')[0]: bot = "dose"
        else: bot = "new"
        await write_usage(session, message.from_user.id, response['input_tokens'], response['output_tokens'], bot=bot)

    return await professor_bot.parse_response(response, message)


@router.message(user_states.Registration.phone, lambda message: message.from_user.id not in ADMIN_TG_IDS)
@router2.message(user_states.Registration.phone, lambda message: message.from_user.id not in ADMIN_TG_IDS)
@router3.message(user_states.Registration.phone, lambda message: message.from_user.id not in ADMIN_TG_IDS)
async def handle_user_registration(message: Message, state: FSMContext, professor_bot, professor_client):
    if not message.contact:
        return await message.answer(
            f"Уважаемый {message.from_user.full_name}, нажмите кнопку ниже ⬇️",
            reply_markup=user_keyboards.phone,
        )

    phone = message.contact.phone_number
    await state.clear()
    thread_id = await professor_bot.create_user(message.from_user.id, phone)
    response = await professor_client.send_message(
        f"Я написал первое сообщение. Мое имя в Telegram — {message.from_user.full_name}.",
        thread_id=thread_id,
    )


    bot_id = str(message.bot.id)
    if bot_id == AI_BOT_TOKEN.split(':')[0]: bot = "professor"
    elif bot_id == AI_BOT_TOKEN2.split(':')[0]: bot = "dose"
    else: bot = "new"

    async with get_session() as session:
        await increment_tokens(session, message.from_user.id, response['input_tokens'], response['output_tokens'])
        await write_usage(session, message.from_user.id, response['input_tokens'], response['output_tokens'], bot=bot)


    return await professor_bot.parse_response(response, message)

@router.message(Command('new_chat'))
@router2.message(Command('new_chat'))
@router3.message(Command('new_chat'))
async def handle_new_chat(message: Message, professor_bot, professor_client):
    thread_id = await professor_client.create_thread()
    async with get_session() as session:
        await update_user(session, message.from_user.id, UserUpdate(thread_id=thread_id))
        professor_bot.users[message.from_user.id]["thread_id"] = thread_id

    await message.answer('Новый чат успешно начат, продолжайте общение')


@router.message(lambda message: message.text, lambda message: message.from_user.id not in ADMIN_TG_IDS)
@router2.message(lambda message: message.text, lambda message: message.from_user.id not in ADMIN_TG_IDS)
@router3.message(lambda message: message.text, lambda message: message.from_user.id not in ADMIN_TG_IDS)
@with_typing
async def handle_text_message(message: Message, state: FSMContext, professor_bot, professor_client):
    user_id = message.from_user.id
    if user_id not in professor_bot.users:
        return await handle_user_start(message, state, professor_bot, professor_client)

    user_data = professor_bot.users[user_id]
    blocked_until = user_data.get("blocked_until")

    if blocked_until and blocked_until > datetime.now(ZoneInfo("Europe/Moscow")):
        return await message.answer(
            f"Уважаемый {message.from_user.full_name}, вы *ЗАБЛОКИРОВАНЫ*.\n\n"
            f"Свяжитесь с поддержкой: @paylakurusyan",
            parse_mode="Markdown",
        )

    thread_id = user_data.get("thread_id")
    response = await professor_client.send_message(message.text, thread_id)

    bot_id = str(message.bot.id)
    if bot_id == AI_BOT_TOKEN.split(':')[0]: bot = "professor"
    elif bot_id == AI_BOT_TOKEN2.split(':')[0]: bot = "dose"
    else: bot = "new"

    async with get_session() as session:
        await increment_tokens(session, message.from_user.id, response['input_tokens'], response['output_tokens']),
        await write_usage(session, message.from_user.id, response['input_tokens'], response['output_tokens'], bot=bot)

    return await professor_bot.parse_response(response, message)
