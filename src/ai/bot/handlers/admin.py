import os
import pandas as pd

from datetime import datetime, date, timedelta
from aiogram import Router
from aiogram.enums import ChatType
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, FSInputFile

from config import ADMIN_TG_IDS, SPENDS_DIR, PROFESSOR_BOT_TOKEN, DOSE_BOT_TOKEN, MOSCOW_TZ
from src.ai.bot.keyboards import admin_keyboards
from src.ai.bot.states import admin_states
from src.helpers import make_excel_safe
from src.tg_methods import get_user_id_by_phone, normalize_phone
from src.webapp import get_session
from src.webapp.crud import get_usages, get_user, update_user, upsert_user, list_promos, get_carts, get_users
from src.webapp.schemas import UserUpdate, UserCreate

professor_admin_router = Router(name="admin_professor")
new_admin_router = Router(name="admin_new")
dose_admin_router = Router(name="admin_dose")

professor_admin_router.message.filter(lambda message: message.from_user.id in ADMIN_TG_IDS and message.chat.type == ChatType.PRIVATE)
professor_admin_router.callback_query.filter(lambda call: call.data.startswith("admin") and call.from_user.id in ADMIN_TG_IDS and call.message.chat.type == ChatType.PRIVATE)
new_admin_router.message.filter(lambda message: message.from_user.id in ADMIN_TG_IDS and message.chat.type == ChatType.PRIVATE)
new_admin_router.callback_query.filter(lambda call: call.data.startswith("admin") and call.from_user.id in ADMIN_TG_IDS and call.message.chat.type == ChatType.PRIVATE)
dose_admin_router.message.filter(lambda message: message.from_user.id in ADMIN_TG_IDS and message.chat.type == ChatType.PRIVATE)
dose_admin_router.callback_query.filter(lambda call: call.data.startswith("admin") and call.from_user.id in ADMIN_TG_IDS and call.message.chat.type == ChatType.PRIVATE)

@new_admin_router.message(Command("send"))
@dose_admin_router.message(Command("send"))
@professor_admin_router.message(Command("send"))
async def handle_send(message: Message):
    args = message.html_text.removeprefix("/send ").strip().split(maxsplit=1)
    who = args[0]
    if who.isdigit():
        user_id = int(who)
        async with get_session() as session: user = await get_user(session, 'tg_id', user_id)
        if user:
            try:
                await message.bot.get_chat(user_id)
                try:
                    await message.bot.send_message(user_id, args[1])
                    await message.answer(f"Сообщение успешно отправлено пользователю с номером {user.tg_phone}")
                except Exception as e: await message.answer(str(e))
            except: await message.answer(f"Чат у пользователя с айди {user.tg_id} не был найден")
        else: await message.answer(f"Пользователь с айди {user_id} не был найден")

    elif who == "all":
        async with get_session() as session: users = await get_users(session)
        i = 0
        for user in users:
            try:
                await message.bot.get_chat(user.tg_id)
                try: await message.bot.send_message(user.tg_id, args[1]); i +=1
                except Exception as e: await message.answer(f"Не удалось отправить сообщение пользователю с номером {user.tg_phone}: {e}")
            except: await message.answer(f"Чат у пользователя с айди {user.tg_id} не был найден")
        await message.answer(f"Успешно разослано {i} пользователям")
    else: await message.answer("Ошибка команды: <code>/send тг_айди/all текст</code>")


@professor_admin_router.message(CommandStart())
@dose_admin_router.message(CommandStart())
async def handle_admin_start(message: Message):
    await message.answer(f'{message.from_user.full_name}, Добро пожаловать в <b>админ панель</b>\n\nВыберите действие кнопками ниже', reply_markup=admin_keyboards.main_menu, parse_mode="html")
    await message.delete()

@professor_admin_router.message(Command('block'))
@new_admin_router.message(Command('block'))
@dose_admin_router.message(Command('block'))
async def handle_block(message: Message):
    text = (message.text or "").strip()
    args = text.removeprefix("/block ").split()

    if len(args) != 2:
        return await message.answer(
            "<b>Ошибка команды</b>\n"
            "<code>/block phone номер_телефона</code>\n"
            "<code>/block id айди_телеграм</code>"
        )

    mode, value = args[0], args[1]
    user_update = UserUpdate(blocked_until=datetime.max.replace(tzinfo=MOSCOW_TZ))
    full_name = "Unknown"

    if mode == "id":
        if not value.isdigit():
            return await message.answer(
                "<b>Ошибка команды:</b> айди должен быть числом\n"
                "<code>/block id 123456789</code>"
            )

        user_id = int(value)
        async with get_session() as session:
            user = await get_user(session, "tg_id", user_id)
            if not user:
                return await message.answer(
                    f"<b>Ошибка команды: пользователь с айди {user_id} не найден</b>"
                )

            await update_user(session, user.tg_id, user_update)

        # попытка достать нормальное имя из Telegram
        try:
            chat = await message.bot.get_chat(user_id)
            if chat:
                full_name = chat.full_name
        except Exception:
            full_name = str(user_id)

        return await message.answer(
            f"Пользователь {full_name} успешно <b>заблокирован</b>\n"
            f"Команда для разблокировки: <code>/unblock id {user_id}</code>"
        )

    elif mode == "phone":
        phone = normalize_phone(value)
        full_name = phone

        async with get_session() as session:
            user = await get_user(session, "tg_phone", phone)
            if not user: user = await get_user(session, "tg_id", f'+{phone}')

        if not user:
            user_id = await get_user_id_by_phone(phone)
            if not user_id:
                return await message.answer(
                    f"<b>Ошибка команды: пользователь с номером +{phone.removeprefix('+')} не найден</b>"
                )

            async with get_session() as session:
                user = await get_user(session, "tg_id", user_id)
                if not user:
                    return await message.answer(
                        f"<b>Ошибка команды: пользователь с номером +{phone.removeprefix('+')} не найден</b>"
                    )

                # блокируем по tg_id (важно — этого не было в твоем коде)
                await update_user(session, user.tg_id, user_update)

        else:
            # если нашли по tg_phone — просто блокируем
            async with get_session() as session:
                await update_user(session, user.tg_id, user_update)

        # попытка достать нормальное имя из Telegram
        try:
            chat = await message.bot.get_chat(user.tg_id)
            if chat:
                full_name = chat.full_name
        except Exception:
            pass

        return await message.answer(
            f"Пользователь {full_name} успешно <b>заблокирован</b>\n"
            f"Команда для разблокировки: <code>/unblock phone +{phone.removeprefix('+')}</code>"
        )

    # ------------- неизвестный режим -------------
    else:
        return await message.answer(
            "<b>Ошибка команды</b>\n"
            "<code>/block phone номер_телефона</code>\n"
            "<code>/block id айди_телеграм</code>"
        )

@professor_admin_router.message(Command('unblock'))
@new_admin_router.message(Command('unblock'))
@dose_admin_router.message(Command('unblock'))
async def handle_unblock(message: Message):
    text = (message.text or "").strip()
    args = text.removeprefix("/unblock ").split()

    if len(args) != 2:
        return await message.answer(
            "<b>Ошибка команды</b>\n"
            "<code>/unblock phone номер_телефона</code>\n"
            "<code>/unblock id айди_телеграм</code>"
        )

    mode, value = args[0], args[1]
    user_update = UserUpdate(blocked_until=None)
    full_name = "Unknown"

    # ------------- /unblock id 123456 -------------
    if mode == "id":
        if not value.isdigit():
            return await message.answer(
                "<b>Ошибка команды:</b> айди должен быть числом\n"
                "<code>/unblock id 123456789</code>"
            )

        user_id = int(value)
        async with get_session() as session:
            user = await get_user(session, "tg_id", user_id)
            if not user:
                return await message.answer(
                    f"<b>Ошибка команды: пользователь с айди {user_id} не найден</b>"
                )

            await update_user(session, user.tg_id, user_update)

        # попытка достать нормальное имя из Telegram
        try:
            chat = await message.bot.get_chat(user_id)
            if chat:
                full_name = chat.full_name
        except Exception:
            full_name = str(user_id)

        return await message.answer(
            f"Пользователь {full_name} успешно <b>разблокирован</b>\n"
            f"Команда для блокировки: <code>/block id {user_id}</code>"
        )

    elif mode == "phone":
        phone = normalize_phone(value)
        full_name = phone

        async with get_session() as session:
            user = await get_user(session, "tg_phone", phone)
            if not user:
                user = await get_user(session, "tg_id", f'+{phone}')

        if not user:
            user_id = await get_user_id_by_phone(phone)
            if not user_id:
                return await message.answer(
                    f"<b>Ошибка команды: пользователь с номером +{phone.removeprefix('+')} не найден</b>"
                )

            async with get_session() as session:
                user = await get_user(session, "tg_id", user_id)
                if not user:
                    return await message.answer(
                        f"<b>Ошибка команды: пользователь с номером +{phone.removeprefix('+')} не найден</b>"
                    )

                await update_user(session, user.tg_id, user_update)

        else:
            async with get_session() as session:  await update_user(session, user.tg_id, user_update)

        try:
            chat = await message.bot.get_chat(user.tg_id)
            if chat: full_name = chat.full_name
        except Exception:
            pass

        return await message.answer(
            f"Пользователь {full_name} успешно <b>разблокирован</b>\n"
            f"Команда для блокировки: <code>/block phone +{phone.removeprefix('+')}</code>"
        )

    # ------------- неизвестный режим -------------
    else:
        return await message.answer(
            "<b>Ошибка команды</b>\n"
            "<code>/unblock phone номер_телефона</code>\n"
            "<code>/unblock id айди_телеграм</code>"
        )

@professor_admin_router.message(admin_states.MainMenu.spends_time)
@new_admin_router.message(admin_states.MainMenu.spends_time)
@dose_admin_router.message(admin_states.MainMenu.spends_time)
async def handle_spends_time(message: Message):
    """
    Handle admin command to generate spending report.
    Requires exactly two dates in format: DD.MM.YYYY DD.MM.YYYY
    Example: 22.09.2025 12.10.2025
    """
    text = message.text.strip()
    dates = text.split()

    if len(dates) != 2:
        return await message.answer(
            (
                "<b>Неверное количество дат.</b>\n"
                "Пожалуйста, укажите <b>ровно две даты</b> через пробел.\n"
                "Пример: <code>22.09.2025 12.10.2025</code>"
            ),
            reply_markup=admin_keyboards.main_menu,
            parse_mode="HTML",
        )

    try:
        start_date = datetime.strptime(dates[0], "%d.%m.%Y").date()
        end_date = datetime.strptime(dates[1], "%d.%m.%Y").date()

        if end_date < start_date:
            raise ValueError("End date is before start date")

    except Exception:
        return await message.answer(
            (
                "<b>Ошибка формата промежутка.</b>\n"
                "Пожалуйста, следуйте примеру:\n"
                "<code>22.09.2025 12.10.2025</code>\n"
                "(можно скопировать по нажатию)"
            ),
            reply_markup=admin_keyboards.main_menu,
            parse_mode="HTML",
        )

    bot_id = str(message.bot.id)
    if bot_id == PROFESSOR_BOT_TOKEN.split(':')[0]:
        bot = "professor"
    elif bot_id == DOSE_BOT_TOKEN.split(':')[0]:
        bot = "dose"
    else:
        bot = "new"

    async with get_session() as session:
        period_label, usages = await get_usages(session, start_date, end_date, bot=bot)

    if not usages:
        return await message.answer(
            f"📭 Нет данных за период {period_label}.",
            reply_markup=admin_keyboards.main_menu,
            parse_mode="HTML",
        )

    df = pd.DataFrame(usages)
    safe_label = period_label.replace(":", "-").replace("/", "-")
    file_path = os.path.join(SPENDS_DIR, f"Расходы {safe_label}.xlsx")
    df.to_excel(file_path, index=False)
    await message.answer_document(
        FSInputFile(file_path),
        caption=f"📊 Файл со статистикой расходов <b>{period_label}</b>",
        parse_mode="HTML",
        reply_markup=admin_keyboards.main_menu,
    )

    return os.remove(file_path)

@professor_admin_router.callback_query()
@dose_admin_router.callback_query()
async def handle_admin_callback(call: CallbackQuery, state: FSMContext):
    try: await call.answer()
    except Exception: pass
    data = (call.data or "").split(":")[1:]  # ["spends"] or ["spends","<n>"]
    if not data or data[0] != "spends": return

    if len(data) == 1:
        await state.set_state(admin_states.MainMenu.spends_time)
        await call.message.edit_text(
            'Выберите <b>временной промежуток</b> за который будете смотреть расходы\n\n'
            'Также можете отправить <i>количество дней цифрой</i> или <i>промежуток</i> вида '
            '<code>22.09.2025 12.10.2025</code>.',
            parse_mode="HTML",
            reply_markup=admin_keyboards.spend_times
        )
        return

    preset = data[1]
    today = date.today()
    if preset == "0": start_date, end_date = date(1970, 1, 1), today
    else:
        try: days = max(1, int(preset))  # 1/7/30
        except ValueError: days = 1
        end_date = today
        start_date = end_date - timedelta(days=days - 1)

    bot_id = str(call.bot.id)
    if bot_id == PROFESSOR_BOT_TOKEN.split(":")[0]: bot = "professor"
    elif bot_id == DOSE_BOT_TOKEN.split(":")[0]: bot = "dose"
    else: bot = "new"
    async with get_session() as session: period_label, usages = await get_usages(session, start_date, end_date, bot=bot)
    df = pd.DataFrame(usages)
    safe_label = (period_label or "").replace(":", "-").replace("/", "-")
    file_path = os.path.join(SPENDS_DIR, f"Расходы {safe_label}.xlsx")
    df.to_excel(file_path, index=False)

    await call.message.answer_document(
        FSInputFile(file_path),
        caption=f"📊 Файл со статистикой расходов всех пользователей <b>{period_label}</b>",
        parse_mode="HTML",
    )
    try: os.remove(file_path)
    except Exception: pass

    await state.clear()
    await call.message.answer(
        f'{call.from_user.full_name}, Добро пожаловать в <b>админ панель</b>\n\nВыберите действие кнопками ниже',
        reply_markup=admin_keyboards.main_menu,
        parse_mode="HTML"
    )
    try: await call.message.delete()
    except Exception: pass
