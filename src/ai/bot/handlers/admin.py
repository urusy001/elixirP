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
    try:
        await call.answer()
    except Exception:
        pass

    data = (call.data or "").split(":")[1:]  # ["spends"] or ["spends","<n>"]
    if not data or data[0] != "spends":
        return

    # 1) Just open the chooser
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

    # 2) Presets from keyboard: admin:spends:1 / 7 / 30 / 0
    from datetime import date, timedelta
    import os
    import pandas as pd
    from aiogram.types import FSInputFile

    preset = data[1]
    today = date.today()
    if preset == "0":
        start_date, end_date = date(1970, 1, 1), today
    else:
        try:
            days = max(1, int(preset))  # 1/7/30
        except ValueError:
            days = 1
        end_date = today
        start_date = end_date - timedelta(days=days - 1)

    # resolve bot per your tokens
    bot_id = str(call.bot.id)
    if bot_id == AI_BOT_TOKEN.split(":")[0]:
        bot = "professor"
    elif bot_id == AI_BOT_TOKEN2.split(":")[0]:
        bot = "dose"
    else:
        bot = "new"

    # query + export
    async with get_session() as session:
        period_label, usages = await get_usages(session, start_date, end_date, bot=bot)

    df = pd.DataFrame(usages)
    safe_label = (period_label or "").replace(":", "-").replace("/", "-")
    file_path = os.path.join(SPENDS_DIR, f"Расходы {safe_label}.xlsx")
    df.to_excel(file_path, index=False)

    await call.message.answer_document(
        FSInputFile(file_path),
        caption=f"📊 Файл со статистикой расходов всех пользователей <b>{period_label}</b>",
        parse_mode="HTML",
    )
    try:
        os.remove(file_path)
    except Exception:
        pass

    # back to main and clean up
    await state.clear()
    await call.message.answer(
        f'{call.from_user.full_name}, Добро пожаловать в <b>админ панель</b>\n\nВыберите действие кнопками ниже',
        reply_markup=admin_keyboards.main_menu,
        parse_mode="HTML"
    )
    try:
        await call.message.delete()
    except Exception:
        pass
