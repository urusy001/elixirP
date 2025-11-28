from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from config import REPORTS_CHANNEL_ID
from src.antispam.bot.handlers.chat import answer_ephemeral, CHAT_USER_FILTER
from src.webapp import get_session
from src.webapp.crud import update_chat_user, get_chat_user
from src.webapp.schemas import ChatUserUpdate

router = Router(name="user")

@router.message(CHAT_USER_FILTER, Command("report"))
async def handle_report(message: Message):
    if not message.reply_to_message or not message.reply_to_message.from_user:
        return await answer_ephemeral(
            message,
            (
                "Ответьте командой <code>/report</code> на сообщение пользователя, "
                "на которого хотите пожаловаться."
            ),
            ttl=90,
        )

    target = message.reply_to_message.from_user

    if message.from_user and target.id == message.from_user.id:
        return await answer_ephemeral(
            message,
            "Нельзя отправить жалобу на самого себя.",
            ttl=60,
        )

    async with get_session() as session:
        user = await get_chat_user(session, target.id)
        times_reported = (user.times_reported if user else 0) + 1
        await update_chat_user(
            session,
            target.id,
            ChatUserUpdate(
                times_reported=times_reported,
                accused_spam=False,
            ),
        )

    await answer_ephemeral(
        message,
        "Спасибо, жалоба отправлена. Администраторы чата смогут её увидеть.",
        ttl=90,
    )

    await message.reply_to_message.forward(REPORTS_CHANNEL_ID)
    return await message.forward(REPORTS_CHANNEL_ID)
