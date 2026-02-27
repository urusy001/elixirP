from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from config import NEW_ASSISTANT_ID, BOT_KEYWORDS
from src.helpers import CHAT_ADMIN_REPLY_FILTER
from src.ai.webapp_client import webapp_client

new_chat_router = Router(name="new_chat")
new_chat_router.message.filter(CHAT_ADMIN_REPLY_FILTER)

@new_chat_router.message(Command('answer_ai'))
async def answer_ai(message: Message, professor_bot, professor_client):
    reply_message = message.reply_to_message
    if isinstance(reply_message, Message):
        text = reply_message.text.strip()
        target_user_id = reply_message.from_user.id
        user = await webapp_client.get_user("tg_id", target_user_id)
        if not user or not user.thread_id:
            thread_id = await professor_client.create_thread()
            user = await webapp_client.upsert_user({"tg_id": target_user_id, "name": reply_message.from_user.first_name, "surname": reply_message.from_user.last_name, "thread_id": thread_id})
        thread_id = user.thread_id
        response = await professor_client.send_message('ОТВЕЧАЙ КРАТКО ОТВЕЧАЙ КРАТКО ОТВЕЧАЙ КРАТКО ОТВЕЧАЙ КРАТКО. ПОСЛЕ ОТВЕТА СКАЖИ МНЕ ПЕРЕЙТИ С ТОБОЙ В ЛИЧНЫЙ ДИАЛОГ ЕСЛИ ЗАХОЧУ ОТВЕТЫ ДЛИННЕЕ'+text, thread_id, NEW_ASSISTANT_ID)
        await webapp_client.increment_tokens(target_user_id, response["input_tokens"], response["output_tokens"])
        await webapp_client.write_usage(target_user_id, response["input_tokens"], response["output_tokens"], BOT_KEYWORDS[NEW_ASSISTANT_ID])
        await message.delete()
        return await professor_bot.parse_response(response, reply_message, back_menu=False)
    else: return False
