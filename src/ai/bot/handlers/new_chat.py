from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from config import NEW_ASSISTANT_ID, BOT_KEYWORDS
from src.helpers import CHAT_ADMIN_REPLY_FILTER
from src.webapp import get_session
from src.webapp.crud import upsert_user, get_user, write_usage, increment_tokens
from src.webapp.schemas import UserCreate

router = Router(name="new_chat")
router.message.filter(CHAT_ADMIN_REPLY_FILTER)

@router.message(Command('answer_ai'))
async def answer_ai(message: Message, professor_bot, professor_client):
    reply_message = message.reply_to_message
    if isinstance(reply_message, Message):
        text = reply_message.text.strip()
        async with get_session() as session:
            user = await get_user(session, 'tg_id', message.from_user.id)
            if not user or user and not user.thread_id:
                thread_id = await professor_client.create_thread()
                user = await upsert_user(session, UserCreate(tg_id=reply_message.from_user.id, name=reply_message.from_user.first_name, surname=reply_message.from_user.last_name, thread_id=thread_id))
            thread_id = user.thread_id
        response = await professor_client.send_message('ОТВЕЧАЙ КРАТКО ОТВЕЧАЙ КРАТКО ОТВЕЧАЙ КРАТКО ОТВЕЧАЙ КРАТКО. ПОСЛЕ ОТВЕТА СКАЖИ МНЕ ПЕРЕЙТИ С ТОБОЙ В ЛИЧНЫЙ ДИАЛОГ ЕСЛИ ЗАХОЧУ ОТВЕТЫ ДЛИННЕЕ'+text, thread_id, NEW_ASSISTANT_ID)
        async with get_session() as session:
            await increment_tokens(session, message.from_user.id, response['input_tokens'], response['output_tokens']),
            await write_usage(session, message.from_user.id, response['input_tokens'], response['output_tokens'], BOT_KEYWORDS[NEW_ASSISTANT_ID])

        await message.delete()
        return await professor_bot.parse_response(response, reply_message, back_menu=False)
    else: return False
