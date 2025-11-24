import asyncio
import random
from datetime import datetime, timedelta

from aiogram import Router, Bot
from aiogram.filters import ChatMemberUpdatedFilter, JOIN_TRANSITION, Command
from aiogram.types import Message, ChatMemberUpdated, PollAnswer, Poll
from sqlalchemy import select

from config import MOSCOW_TZ, ELIXIR_CHAT_ID, REPORTS_CHANNEL_ID
from src.antispam.bot.permissions import NEW_USER, USER_PASSED
from src.antispam.poll_questions import POLL_QUESTIONS_RU, PollQuestion
from src.antispam.test_classifier import is_spam
from src.helpers import append_message_to_csv, _notify_user, CHAT_ADMIN_FILTER
from src.webapp.models import ChatUser
from src.webapp.schemas import ChatUserCreate
from src.webapp.crud import (
    upsert_chat_user,
    set_muted_until,
    increment_messages_sent,
    increment_times_reported,
    get_chat_user,
    set_whitelist,
    increment_times_muted,
    set_banned_until,
    increment_times_banned,
)
from src.webapp.database import get_session

router = Router(name="chat")

CHAT_USER_FILTER = lambda obj: getattr(obj.chat, "id", 0) in [-1003182914098, ELIXIR_CHAT_ID]

CAPTCHA_MAX_ATTEMPTS = 3


async def safe_restrict(bot: Bot, chat_id: int, user_id: int, permissions) -> bool:
    try:
        member = await bot.get_chat_member(chat_id, user_id)
    except Exception:
        return False
    if member.status in ("left", "kicked"):
        return False
    try:
        await bot.restrict_chat_member(chat_id, user_id, permissions)
        return True
    except Exception:
        return False


async def safe_unrestrict(bot: Bot, chat_id: int, user_id: int) -> bool:
    return await safe_restrict(bot, chat_id, user_id, USER_PASSED)


async def pass_user(chat_id: int, user_id: int, bot: Bot, timer: int | float | None = 24 * 60 * 60):
    await asyncio.sleep(timer)
    await safe_unrestrict(bot, chat_id, user_id)
    async with get_session() as session:
        await set_muted_until(session, user_id, None)


async def start_captcha(bot: Bot, chat_id: int, user_id: int):
    now = datetime.now(tz=MOSCOW_TZ)
    async with get_session() as session:
        user = await get_chat_user(session, user_id)
        if user is None:
            user = await upsert_chat_user(
                session,
                ChatUserCreate(
                    id=user_id,
                    full_name="",
                    username=None,
                    passed_poll=False,
                    whitelist=False,
                    muted_until=None,
                    times_muted=0,
                    banned_until=None,
                    times_banned=0,
                    messages_sent=0,
                    times_reported=0,
                    accused_spam=False,
                    last_accused_text=None,
                    poll_attempts=0,
                    poll_active=False,
                    poll_message_id=None,
                    poll_chat_id=None,
                    poll_id=None,
                    poll_correct_option_id=None,
                ),
            )

        # Уже забанен навсегда
        if user.banned_until and user.banned_until > now + timedelta(days=365 * 10):
            return

        # Лимит попыток уже превышен – ничего не отправляем
        if user.poll_attempts >= CAPTCHA_MAX_ATTEMPTS and not user.passed_poll:
            text = (
                f'<a href="tg://user?id={user_id}">Пользователь</a> не прошёл проверку.\n'
                "Права на отправку сообщений ограничены до решения администратора."
            )
            await bot.send_message(chat_id, text, parse_mode="HTML")
            return

        # Уже есть активный опрос – просим ответить на него
        if user.poll_active and user.poll_chat_id and user.poll_message_id:
            text = (
                f'<a href="tg://user?id={user_id}">Пользователь</a>, '
                "у вас уже есть активный вопрос выше. Сначала ответьте на него."
            )
            await bot.send_message(chat_id, text, parse_mode="HTML")
            return

        # Отправляем новый опрос
        poll_question: PollQuestion = random.choice(POLL_QUESTIONS_RU)
        question = poll_question.text
        options, correct_option_id = poll_question.options(True)

        info_text = (
            "Для отправки сообщений в чат необходимо пройти простую проверку.\n"
            "Ответьте на вопрос ниже. Всего доступно три попытки."
        )
        await bot.send_message(chat_id, info_text)

        poll_message = await bot.send_poll(
            chat_id=chat_id,
            question=question,
            options=options,
            type="quiz",
            correct_option_id=correct_option_id,
            is_anonymous=False,
            open_period=60,
        )

        # Сохраняем состояние капчи в БД
        user.poll_active = True
        user.poll_chat_id = chat_id
        user.poll_message_id = poll_message.message_id
        user.poll_id = poll_message.poll.id
        user.poll_correct_option_id = correct_option_id
        await session.commit()


@router.chat_member(CHAT_USER_FILTER, ChatMemberUpdatedFilter(JOIN_TRANSITION))
async def handle_new_member(event: ChatMemberUpdated):
    user = event.new_chat_member.user
    if user.is_bot:
        return

    async with get_session() as session:
        await upsert_chat_user(
            session,
            ChatUserCreate(
                id=user.id,
                full_name=user.full_name or "",
                username=user.username,
                passed_poll=False,
                whitelist=False,
                muted_until=None,
                times_muted=0,
                banned_until=None,
                times_banned=0,
                messages_sent=0,
                times_reported=0,
                accused_spam=False,
                last_accused_text=None,
                poll_attempts=0,
                poll_active=False,
                poll_message_id=None,
                poll_chat_id=None,
                poll_id=None,
                poll_correct_option_id=None,
            ),
        )


@router.poll_answer()
async def handle_poll_answer(answer: PollAnswer, bot: Bot):
    user_id = answer.user.id
    poll_id = answer.poll_id
    chosen = answer.option_ids[0] if answer.option_ids else None

    now = datetime.now(tz=MOSCOW_TZ)
    async with get_session() as session:
        user = await get_chat_user(session, user_id)
        if not user or user.passed_poll:
            return

        # Проверяем, что это именно его активный опрос
        if not user.poll_active or not user.poll_id or user.poll_id != poll_id:
            return

        chat_id = user.poll_chat_id
        msg_id = user.poll_message_id

        # Удаляем сообщение с опросом
        if chat_id and msg_id:
            try:
                await bot.delete_message(chat_id, msg_id)
            except Exception:
                pass

        # Сбрасываем признак активного опроса
        user.poll_active = False
        user.poll_chat_id = None
        user.poll_message_id = None
        user.poll_id = None

        correct_id = user.poll_correct_option_id

        if chosen is not None and correct_id is not None and chosen == correct_id:
            # Успешное прохождение
            user.passed_poll = True
            user.poll_correct_option_id = None
            await session.commit()

            text = (
                f"{answer.user.mention_html()}, проверка пройдена.\n"
                "Теперь вы можете отправлять сообщения в чат."
            )
            await bot.send_message(chat_id, text, parse_mode="HTML")
            return

        # Неверный ответ – считаем попытку
        user.poll_attempts = (user.poll_attempts or 0) + 1
        attempts = user.poll_attempts
        user.poll_correct_option_id = None

        if attempts >= CAPTCHA_MAX_ATTEMPTS:
            # Блокируем
            far_future = now + timedelta(days=365 * 100)
            user.banned_until = far_future
            user.muted_until = far_future
            await increment_times_banned(session, user_id, 1)
            await session.commit()

            await safe_restrict(bot, chat_id, user_id, NEW_USER)

            text = (
                f"{answer.user.mention_html()}, проверка не пройдена.\n"
                "Количество попыток исчерпано. Права на отправку сообщений ограничены до решения администратора."
            )
            await bot.send_message(chat_id, text, parse_mode="HTML")
        else:
            await session.commit()
            left = CAPTCHA_MAX_ATTEMPTS - attempts
            text = (
                f"{answer.user.mention_html()}, ответ неверный.\n"
                f"Осталось попыток: {left}. Для новой попытки отправьте любое сообщение в чат."
            )
            await bot.send_message(chat_id, text, parse_mode="HTML")


@router.poll()
async def handle_poll_expired(poll: Poll, bot: Bot):
    now = datetime.now(tz=MOSCOW_TZ)
    async with get_session() as session:
        result = await session.execute(
            select(ChatUser).where(ChatUser.poll_id == poll.id)
        )
        user = result.scalars().first()
        if not user or user.passed_poll is True:
            return

        chat_id = user.poll_chat_id
        msg_id = user.poll_message_id
        user_id = user.id

        if chat_id and msg_id:
            try:
                await bot.delete_message(chat_id, msg_id)
            except Exception:
                pass

        # Сбрасываем активный опрос
        user.poll_active = False
        user.poll_chat_id = None
        user.poll_message_id = None
        user.poll_id = None
        user.poll_correct_option_id = None

        # Считаем попытку
        user.poll_attempts = (user.poll_attempts or 0) + 1
        attempts = user.poll_attempts

        if attempts >= CAPTCHA_MAX_ATTEMPTS:
            far_future = now + timedelta(days=365 * 100)
            user.banned_until = far_future
            user.muted_until = far_future
            await increment_times_banned(session, user_id, 1)
            await session.commit()

            await safe_restrict(bot, chat_id, user_id, NEW_USER)

            text = (
                f'<a href="tg://user?id={user_id}">Пользователь</a> не прошёл проверку.\n'
                "Количество попыток исчерпано. Права на отправку сообщений ограничены до решения администратора."
            )
            await bot.send_message(chat_id, text, parse_mode="HTML")
        else:
            await session.commit()
            left = CAPTCHA_MAX_ATTEMPTS - attempts
            text = (
                f'<a href="tg://user?id={user_id}">Пользователь</a> не успел ответить на проверочный вопрос.\n'
                f"Осталось попыток: {left}. Для новой попытки нужно отправить сообщение в чат."
            )
            await bot.send_message(chat_id, text, parse_mode="HTML")


@router.message(CHAT_ADMIN_FILTER, Command("spam"))
async def handle_spam(message: Message):
    if not message.reply_to_message:
        asyncio.create_task(
            _notify_user(message, "<b>Ошибка команды: </b>отвечайте командой на нужное сообщение", 60)
        )
        return
    if not message.reply_to_message.text:
        asyncio.create_task(
            _notify_user(message, "Сообщение без текста, пометить как спам нельзя.", 60)
        )
        return

    target = message.reply_to_message.from_user
    await append_message_to_csv(message.reply_to_message.text.strip(), 1)

    async with get_session() as session:
        await increment_times_reported(
            session,
            target.id,
            delta=1,
            accused_spam=True,
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
        asyncio.create_task(
            _notify_user(message, "<b>Ошибка команды: </b>отвечайте командой на нужное сообщение", 60)
        )
        return

    chat_id = message.chat.id
    target = message.reply_to_message.from_user
    minutes_str = message.text.strip().removeprefix("/mute").strip()
    timer = float(minutes_str) * 60 if minutes_str.isdigit() else None

    if timer:
        async with get_session() as session:
            await set_muted_until(
                session,
                target.id,
                datetime.now(tz=MOSCOW_TZ) + timedelta(seconds=timer),
                )
            await increment_times_muted(session, target.id, 1)
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
        return asyncio.create_task(
            _notify_user(
                message,
                (
                    "<b>Использование:</b>\n"
                    "<code>/whitelist add [user_id]</code> — добавить в белый список\n"
                    "<code>/whitelist remove [user_id]</code> — убрать из белого списка\n\n"
                    "Можно указать <code>user_id</code> или ответить командой на сообщение пользователя."
                ),
                180,
            )
        )

    action = args[0].lower()
    if action in ("add", "on", "+"):
        value = True
    elif action in ("remove", "rm", "off", "del", "-"):
        value = False
    else:
        return asyncio.create_task(
            _notify_user(
                message,
                "<b>Ошибка команды:</b> неизвестное действие.\n"
                "Используйте <code>add</code> или <code>remove</code>.",
                120,
            )
        )

    user_id: int | None = None

    if len(args) >= 2 and args[1].isdigit():
        user_id = int(args[1])
    elif message.reply_to_message and message.reply_to_message.from_user:
        user_id = message.reply_to_message.from_user.id

    if not user_id:
        return asyncio.create_task(
            _notify_user(
                message,
                (
                    "Укажите <code>user_id</code> или ответьте командой на сообщение пользователя.\n\n"
                    "<b>Пример:</b> <code>/whitelist add 123456789</code>"
                ),
                150,
            )
        )

    async with get_session() as session:
        user = await set_whitelist(session, user_id, value)

    if not user:
        return asyncio.create_task(
            _notify_user(
                message,
                (
                    "Пользователь не найден в базе.\n"
                    "Он должен хотя бы один раз написать в чат, чтобы бот его сохранил."
                ),
                120,
            )
        )

    status = "добавлен в <b>белый список</b>" if value else "убран из <b>белого списка</b>"

    return asyncio.create_task(
        _notify_user(
            message,
            f"Пользователь с <code>user_id={user_id}</code> {status}.",
            90,
        )
    )


@router.message(CHAT_ADMIN_FILTER, Command("unmute"))
async def handle_unmute(message: Message):
    text = message.text or ""
    user_id_str = text.strip().removeprefix("/unmute").strip()
    user_id = int(user_id_str) if user_id_str.isdigit() else None

    if not user_id and message.reply_to_message:
        user_id = message.reply_to_message.from_user.id

    if not user_id:
        return asyncio.create_task(
            _notify_user(
                message,
                (
                    "Либо укажите user_id пользователя, либо ответьте командой на его сообщение\n\n"
                    "<i>Напишите @ShostakovIV в ТГ, если не знаете как получить user_id</i>"
                ),
                120,
            )
        )

    ok = await safe_unrestrict(message.bot, message.chat.id, user_id)

    async with get_session() as session:
        await set_muted_until(session, user_id, None)

    msg = (
        "Пользователю успешно возвращены права"
        if ok
        else "Не удалось вернуть права: пользователь не найден или уже покинул чат"
    )

    return asyncio.create_task(_notify_user(message, msg, 60))


@router.message(CHAT_USER_FILTER, Command("report"))
async def handle_report(message: Message):
    if not message.reply_to_message or not message.reply_to_message.from_user:
        asyncio.create_task(
            _notify_user(
                message,
                (
                    "Ответьте командой <code>/report</code> на сообщение пользователя, "
                    "на которого хотите пожаловаться."
                ),
                90,
            )
        )
        return

    target = message.reply_to_message.from_user

    if message.from_user and target.id == message.from_user.id:
        asyncio.create_task(
            _notify_user(
                message,
                "Нельзя отправить жалобу на самого себя.",
                60,
            )
        )
        return

    async with get_session() as session:
        await increment_times_reported(
            session,
            target.id,
            delta=1,
            accused_spam=False,
        )

    asyncio.create_task(
        _notify_user(
            message,
            "Спасибо, жалоба отправлена. Администраторы чата смогут её увидеть.",
            90,
        )
    )

    await message.reply_to_message.forward(REPORTS_CHANNEL_ID)
    await message.forward(REPORTS_CHANNEL_ID)


@router.message(CHAT_ADMIN_FILTER, Command("get_id"))
async def handle_get_id(message: Message):
    return await message.answer(f"{message.chat.id}")


@router.message(CHAT_USER_FILTER)
async def handle_chat_message(message: Message):
    if not message.text or not message.text.strip():
        return

    user = message.from_user
    if not user:
        return

    now = datetime.now(tz=MOSCOW_TZ)
    whitelist = await CHAT_ADMIN_FILTER(message, message.bot)

    async with get_session() as session:
        chat_user = await get_chat_user(session, user.id)

        if chat_user is None:
            # Старые участники до внедрения капчи
            chat_user = await upsert_chat_user(
                session,
                ChatUserCreate(
                    id=user.id,
                    full_name=user.full_name or "",
                    username=user.username,
                    passed_poll=True,
                    whitelist=False,
                    muted_until=None,
                    times_muted=0,
                    banned_until=None,
                    times_banned=0,
                    messages_sent=1,
                    times_reported=0,
                    accused_spam=False,
                    last_accused_text=None,
                    poll_attempts=0,
                    poll_active=False,
                    poll_message_id=None,
                    poll_chat_id=None,
                    poll_id=None,
                    poll_correct_option_id=None,
                ),
            )
            passed_poll = True
        else:
            whitelist = whitelist or bool(chat_user.whitelist)
            passed_poll = bool(chat_user.passed_poll)
            await increment_messages_sent(session, user.id, 1)

        # Если бессрочно забанен – на всякий случай ещё раз ограничиваем и удаляем сообщение
        if chat_user.banned_until and chat_user.banned_until > now + timedelta(days=365 * 10):
            await safe_restrict(message.bot, message.chat.id, user.id, NEW_USER)
            try:
                await message.delete()
            except Exception:
                pass
            return

    # Админы и whitelisted проходят без проверки
    if whitelist:
        await append_message_to_csv(message.text, 0)
        return

    # Пользователь ещё не прошёл капчу – запускаем / напоминаем
    if not passed_poll:
        await start_captcha(message.bot, message.chat.id, user.id)
        try:
            await message.delete()
        except Exception:
            pass
        return

    # ===== АНТИСПАМ =====
    result, p = await is_spam(message.text)
    print(result, p, message.text)

    if result:
        async with get_session() as session:
            chat_user = await get_chat_user(session, user.id)
            times_muted = chat_user.times_muted if chat_user and chat_user.times_muted is not None else 0

            await increment_times_reported(session, user.id, delta=1, accused_spam=True)

            # p >= 0.8 → бессрочный мут
            if p >= 0.8:
                far_future = now + timedelta(days=365 * 100)
                await set_banned_until(session, user.id, far_future)
                await set_muted_until(session, user.id, far_future)
                await increment_times_banned(session, user.id, 1)

                await safe_restrict(message.bot, message.chat.id, user.id, NEW_USER)

                text = (
                    "Сообщение с очень высокой вероятностью является спамом.\n"
                    f"Пользователь {user.mention_html()} ограничен в отправке сообщений <b>без срока</b>."
                )
                await message.answer(text, parse_mode="HTML")

            else:
                # Лестница: 1-й раз – без мута, далее 1д / 7д / 30д / бесконечно
                await increment_times_muted(session, user.id, 1)
                new_count = times_muted + 1

                # 1-й раз – только удаляем и предупреждаем
                if new_count == 1:
                    text = (
                        "Сообщение похоже на спам.\n"
                        "Сообщение удалено. Это первое предупреждение, ограничения не выданы."
                    )
                    await message.answer(text, parse_mode="HTML")
                else:
                    if new_count == 2:
                        mute_delta = timedelta(days=1)
                    elif new_count == 3:
                        mute_delta = timedelta(weeks=1)
                    elif new_count == 4:
                        mute_delta = timedelta(days=30)
                    else:
                        mute_delta = None  # дальше бессрочно

                    if mute_delta is None:
                        far_future = now + timedelta(days=365 * 100)
                        await set_banned_until(session, user.id, far_future)
                        await set_muted_until(session, user.id, far_future)
                        await increment_times_banned(session, user.id, 1)
                        await safe_restrict(message.bot, message.chat.id, user.id, NEW_USER)

                        text = (
                            "Сообщение похоже на спам.\n"
                            f"Пользователь {user.mention_html()} ограничен в отправке сообщений <b>без срока</b> "
                            "из-за повторяющегося спама."
                        )
                        await message.answer(text, parse_mode="HTML")
                    else:
                        mute_until = now + mute_delta
                        await set_muted_until(session, user.id, mute_until)
                        await safe_restrict(message.bot, message.chat.id, user.id, NEW_USER)

                        if mute_delta.days >= 30:
                            label = "на 1 месяц"
                        elif mute_delta.days >= 7:
                            label = "на 1 неделю"
                        elif mute_delta.days >= 1:
                            label = "на 1 день"
                        else:
                            label = "временно"

                        text = (
                            "Сообщение похоже на спам.\n"
                            f"Пользователь {user.mention_html()} автоматически ограничен в правах {label}.\n"
                            f"Для досрочного возвращения прав используйте команду <code>/unmute {user.id}</code>"
                        )
                        await message.answer(text, parse_mode="HTML")
                        asyncio.create_task(
                            pass_user(
                                message.chat.id,
                                user.id,
                                message.bot,
                                mute_delta.total_seconds(),
                            )
                        )

        try:
            await message.delete()
        except Exception:
            pass

    await append_message_to_csv(message.text, int(result))