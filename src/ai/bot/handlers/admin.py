import os
import pandas as pd

from datetime import datetime, date
from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.filters import CommandStart
from src.ai.bot.keyboards import admin_keyboards
from src.ai.bot.states import admin_states

from config import ADMIN_TG_IDS, SPENDS_DIR, AI_BOT_TOKEN, AI_BOT_TOKEN2
from src.webapp import get_session
from src.webapp.crud import get_usages


router = Router(name="admin")
router2 = Router(name="admin")
router3 = Router(name="admin")


@router.message(CommandStart(), lambda message: message.from_user.id in ADMIN_TG_IDS)
@router2.message(CommandStart(), lambda message: message.from_user.id in ADMIN_TG_IDS)
@router3.message(CommandStart(), lambda message: message.from_user.id in ADMIN_TG_IDS)
async def handle_admin_start(message: Message):
    await message.answer(f'{message.from_user.full_name}, Добро пожаловать в <b>админ панель</b>\n\nВыберите действие кнопками ниже', reply_markup=admin_keyboards.main_menu, parse_mode="html")

@router.message(admin_states.MainMenu.spends_time, lambda message: message.from_user.id in ADMIN_TG_IDS)
@router2.message(admin_states.MainMenu.spends_time, lambda message: message.from_user.id in ADMIN_TG_IDS)
@router3.message(admin_states.MainMenu.spends_time, lambda message: message.from_user.id in ADMIN_TG_IDS)
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
    if bot_id == AI_BOT_TOKEN.split(':')[0]: bot = "professor"
    elif bot_id == AI_BOT_TOKEN2.split(':')[0]: bot = "dose"
    else: bot = "new"


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


@router.callback_query(lambda call: call.data.startswith("admin") and call.from_user.id in ADMIN_TG_IDS)
@router2.callback_query(lambda call: call.data.startswith("admin") and call.from_user.id in ADMIN_TG_IDS)
@router3.callback_query(lambda call: call.data.startswith("admin") and call.from_user.id in ADMIN_TG_IDS)
async def handle_admin_callback(call: CallbackQuery, state: FSMContext):
    data = call.data.split(":")[1:]
    current_state = await state.get_state()
    state_data = await state.get_data()
    if data[0] == 'spends':
        if len(data) == 1:
            await state.set_state(admin_states.MainMenu.spends_time)
            await call.message.edit_text('Выберите <b>временной промежуток</b> за который будете смотреть расходы\n\nТакже можете отправить <i>количество дней цифрой или временной промежуток.</i>\nФормат промежутка: <code>22.09.2025 12.10.2025</code>', parse_mode="html", reply_markup=admin_keyboards.spend_times)

        elif len(data) >= 2 and current_state == admin_states.MainMenu.spends_time:
            try:
                date_parts = data[1:]
                parsed_dates = [datetime.strptime(d, "%d.%m.%Y").date() for d in date_parts]
                start_date = parsed_dates[0]
                end_date = parsed_dates[1] if len(parsed_dates) > 1 else date.today()

            except Exception:
                start_date = date.today()
                end_date = date.today()

            bot_id = str(call.bot.id)
            if bot_id == AI_BOT_TOKEN.split(':')[0]: bot = "professor"
            elif bot_id == AI_BOT_TOKEN2.split(':')[0]: bot = "dose"
            else: bot = "new"

            async with get_session() as session: period_label, usages = await get_usages(session, start_date, end_date, bot=bot)

            df = pd.DataFrame(usages)
            safe_label = period_label.replace(":", "-").replace("/", "-")
            file_path = os.path.join(SPENDS_DIR, f"Расходы {safe_label}.xlsx")
            df.to_excel(file_path, index=False)
            await call.message.answer_document(
                FSInputFile(file_path),
                caption=(
                    f"📊 Файл со статистикой расходов всех пользователей "
                    f"<b>{period_label}</b>"
                ),
                parse_mode="HTML",
            )
            os.remove(file_path)
            await call.message.answer(
                f'{call.from_user.full_name}, Добро пожаловать в <b>админ панель</b>\n\nВыберите действие кнопками ниже',
                reply_markup=admin_keyboards.main_menu, parse_mode="html")
            await call.message.delete()
