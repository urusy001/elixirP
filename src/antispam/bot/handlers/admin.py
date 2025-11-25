import asyncio
from datetime import timedelta, datetime

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from config import REPORTS_CHANNEL_ID, MOSCOW_TZ
from src.antispam.bot.handlers.chat import answer_ephemeral, CHAT_USER_FILTER, safe_unrestrict, safe_restrict, pass_user
from src.antispam.bot.permissions import NEW_USER
from src.helpers import CHAT_ADMIN_FILTER, _notify_user, append_message_to_csv
from src.webapp import get_session
from src.webapp.crud import update_chat_user, get_chat_user
from src.webapp.schemas import ChatUserUpdate

router = Router(name="admin")

# ==========================
#  АДМИН-КОМАНДЫ: SPAM / MUTE / WHITELIST / UNMUTE / REPORT / GET_ID
# ==========================

@router.message(CHAT_ADMIN_FILTER, Command("spam"))
async def handle_spam(message: Message):
    if not message.reply_to_message:
        await answer_ephemeral(
            message,
            "<b>Ошибка команды: </b>отвечайте командой на нужное сообщение",
            ttl=60,
        )
        return
    if not message.reply_to_message.text:
        await answer_ephemeral(
            message,
            "Сообщение без текста, пометить как спам нельзя.",
            ttl=60,
        )
        return

    target = message.reply_to_message.from_user
    spam_text = message.reply_to_message.text.strip()
    await append_message_to_csv(spam_text, 1)

    async with get_session() as session:
        user = await get_chat_user(session, target.id)
        times_reported = (user.times_reported if user else 0) + 1
        await update_chat_user(
            session,
            target.id,
            ChatUserUpdate(
                times_reported=times_reported,
                accused_spam=True,
                last_accused_text=spam_text,
            ),
        )

    await safe_restrict(message.bot, message.chat.id, target.id, NEW_USER)

    asyncio.create_task(
        _notify_user(
            message,
            (
                f"Сообщение маркировано как <b>спам</b>, пользователь {target.mention_html()} <b>ограничен</b>\n"
                f"Для возвращения прав используйте команду <code>/unmute {target.id}</code>"
            ),
            300,
        )
    )

    try:
        await message.reply_to_message.delete()
    except Exception:
        pass


@router.message(CHAT_ADMIN_FILTER, Command("mute"))
async def handle_mute(message: Message):
    if not message.reply_to_message:
        await answer_ephemeral(
            message,
            "<b>Ошибка команды: </b>отвечайте командой на нужное сообщение",
            ttl=60,
        )
        return

    chat_id = message.chat.id
    target = message.reply_to_message.from_user
    minutes_str = message.text.strip().removeprefix("/mute").strip()
    timer = float(minutes_str) * 60 if minutes_str.isdigit() else None

    if timer:
        mute_until = datetime.now(tz=MOSCOW_TZ) + timedelta(seconds=timer)
        async with get_session() as session:
            user = await get_chat_user(session, target.id)
            times_muted = (user.times_muted if user else 0) + 1
            await update_chat_user(
                session,
                target.id,
                ChatUserUpdate(
                    muted_until=mute_until,
                    times_muted=times_muted,
                ),
            )
        asyncio.create_task(pass_user(chat_id, target.id, message.bot, timer))

    await safe_restrict(message.bot, chat_id, target.id, NEW_USER)
    label = "" if not timer else f" на {minutes_str} минут"

    asyncio.create_task(
        _notify_user(
            message,
            (
                f"Пользователь {target.mention_html()} успешно <b>ограничен в правах{label}</b>\n"
                f"Для возвращения прав используйте команду <code>/unmute {target.id}</code>"
            ),
            300,
        )
    )


@router.message(CHAT_ADMIN_FILTER, Command("whitelist"))
async def handle_whitelist(message: Message):
    text = message.text or ""
    args = text.strip().removeprefix("/whitelist").strip().split()

    if not args:
        return await answer_ephemeral(
            message,
            (
                "<b>Использование:</b>\n"
                "<code>/whitelist add [user_id]</code> — добавить в белый список\n"
                "<code>/whitelist remove [user_id]</code> — убрать из белого списка\n\n"
                "Можно указать <code>user_id</code> или ответить командой на сообщение пользователя."
            ),
            ttl=180,
        )

    action = args[0].lower()
    if action in ("add", "on", "+"):
        value = True
    elif action in ("remove", "rm", "off", "del", "-"):
        value = False
    else:
        return await answer_ephemeral(
            message,
            "<b>Ошибка команды:</b> неизвестное действие.\n"
            "Используйте <code>add</code> или <code>remove</code>.",
            ttl=120,
        )

    user_id: int | None = None

    if len(args) >= 2 and args[1].isdigit():
        user_id = int(args[1])
    elif message.reply_to_message and message.reply_to_message.from_user:
        user_id = message.reply_to_message.from_user.id

    if not user_id:
        return await answer_ephemeral(
            message,
            (
                "Укажите <code>user_id</code> или ответьте командой на сообщение пользователя.\n\n"
                "<b>Пример:</b> <code>/whitelist add 123456789</code>"
            ),
            ttl=150,
        )

    async with get_session() as session:
        user = await update_chat_user(session, user_id, ChatUserUpdate(whitelist=value))

    if not user:
        return await answer_ephemeral(
            message,
            (
                "Пользователь не найден в базе.\n"
                "Он должен хотя бы один раз написать в чат, чтобы бот его сохранил."
            ),
            ttl=120,
        )

    status = "добавлен в <b>белый список</b>" if value else "убран из <b>белого списка</b>"

    return await answer_ephemeral(
        message,
        f"Пользователь с <code>user_id={user_id}</code> {status}.",
        ttl=90,
    )


@router.message(CHAT_ADMIN_FILTER, Command("unmute"))
async def handle_unmute(message: Message):
    text = message.text or ""
    user_id_str = text.strip().removeprefix("/unmute").strip()
    user_id = int(user_id_str) if user_id_str.isdigit() else None

    if not user_id and message.reply_to_message:
        user_id = message.reply_to_message.from_user.id

    if not user_id:
        return await answer_ephemeral(
            message,
            (
                "Либо укажите user_id пользователя, либо ответьте командой на его сообщение\n\n"
                "<i>Напишите @ShostakovIV в ТГ, если не знаете как получить user_id</i>"
            ),
            ttl=120,
        )

    ok = await safe_unrestrict(message.bot, message.chat.id, user_id)

    async with get_session() as session:
        await update_chat_user(session, user_id, ChatUserUpdate(muted_until=None))

    msg = (
        "Пользователю успешно возвращены права"
        if ok
        else "Не удалось вернуть права: пользователь не найден или уже покинул чат"
    )

    return await answer_ephemeral(message, msg, ttl=60)


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
    await message.forward(REPORTS_CHANNEL_ID)


@router.message(CHAT_ADMIN_FILTER, Command("get_thread"))
async def handle_get_id(message: Message):
    return await answer_ephemeral(message.message_thread_id, f"{message.chat.id}", ttl=30)
