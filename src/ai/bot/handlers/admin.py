import os
from datetime import datetime

import pandas as pd
from aiogram import Router
from aiogram.enums import ChatType
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, FSInputFile

from config import OWNER_TG_IDS, SPENDS_DIR, PROFESSOR_BOT_TOKEN, DOSE_BOT_TOKEN, MOSCOW_TZ
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

professor_admin_router.message.filter(lambda message: message.from_user.id in OWNER_TG_IDS and message.chat.type == ChatType.PRIVATE)
professor_admin_router.callback_query.filter(lambda call: call.data.startswith("admin") and call.from_user.id in OWNER_TG_IDS and call.message.chat.type == ChatType.PRIVATE)
new_admin_router.message.filter(lambda message: message.from_user.id in OWNER_TG_IDS and message.chat.type == ChatType.PRIVATE)
new_admin_router.callback_query.filter(lambda call: call.data.startswith("admin") and call.from_user.id in OWNER_TG_IDS and call.message.chat.type == ChatType.PRIVATE)
dose_admin_router.message.filter(lambda message: message.from_user.id in OWNER_TG_IDS and message.chat.type == ChatType.PRIVATE)
dose_admin_router.callback_query.filter(lambda call: call.data.startswith("admin") and call.from_user.id in OWNER_TG_IDS and call.message.chat.type == ChatType.PRIVATE)

@new_admin_router.message(Command("send"))
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
            except: pass
        else: await message.answer(f"Пользователь с айди {user_id} не был найден")

    elif who == "all":
        async with get_session() as session: users = await get_users(session)
        i = 0
        for user in users:
            try:
                await message.bot.get_chat(user.tg_id)
                try: await message.bot.send_message(user.tg_id, args[1]); i +=1
                except Exception as e: await message.answer(f"Не удалось отправить сообщение пользователю с номером {user.tg_phone}: {e}")
            except: pass
        await message.answer(f"Успешно разослано {i} пользователям")
    else: await message.answer("Ошибка команды: <code>/send тг_айди/all текст</code>")


@new_admin_router.message(Command('edit_and_pin'), lambda message: message.reply_to_message)
async def handle_pin(message: Message):
    forwarded_message = message.reply_to_message
    print(forwarded_message.html_text)
    c_id = forwarded_message.forward_from_chat.id
    m_id = forwarded_message.forward_from_message_id
    await message.bot.edit_message_reply_markup(message_id=m_id,  chat_id=c_id, reply_markup=admin_keyboards.open_test)

@new_admin_router.message(Command('set_premium'))
async def add_premium(message: Message):
    args = message.text.removeprefix("/set_premium ").strip().split()
    if len(args) == 2:
        phone = normalize_phone(args[1])
        async with get_session() as session:
            user = await get_user(session, 'tg_phone', phone)

        user_id = await get_user_id_by_phone(phone) if not (user and user.tg_id) else user.tg_id
        if not user_id: return await message.answer('Пользователь не найден по номеру в ТГ')
    else: return await message.answer('Ошибка команды: <code>/set_premium количество номер_в_тг</code>')
    amount = args[0]
    if not (amount.isdigit() and int(amount) > 0): return await message.answer('Ошибка команды')
    async with get_session() as session: user = await update_user(session, int(user_id), UserUpdate(premium_requests=int(amount)))
    if user: return await message.answer(f'Премиум запросы для пользователя обновлены на {amount}')
    else:
        async with get_session() as session: user = await upsert_user(session, UserCreate(tg_phone=phone, tg_id=user_id, premium_requests=int(amount)))
        if user: await message.answer(f'Премиум запросы для пользователя успешно обновлены на {amount}')
        else: await message.answer("Ошибка команды: пользователь не пользовался ботом или айди неверное")
        return None

@new_admin_router.message(Command("statistics"))
async def handle_statistics(message: Message):
    async with get_session() as session:
        promos = await list_promos(session)
        carts = await get_carts(session)

    promos_rows = []
    for p in promos:
        promos_rows.append({
            "ID": getattr(p, "id", None),
            "Промокод": getattr(p, "code", None),
            "Скидка, %": float(getattr(p, "discount_pct", 0) or 0),
            "Владелец": getattr(p, "owner_name", None),
            "Процент владельца, %": float(getattr(p, "owner_pct", 0) or 0),
            "Начислено владельцу, ₽": float(getattr(p, "owner_amount_gained", 0) or 0),
            "Уровень 1 (имя)": getattr(p, "lvl1_name", None),
            "Уровень 1 (процент), %": float(getattr(p, "lvl1_pct", 0) or 0),
            "Уровень 1 (начислено), ₽": float(getattr(p, "lvl1_amount_gained", 0) or 0),
            "Уровень 2 (имя)": getattr(p, "lvl2_name", None),
            "Уровень 2 (процент), %": float(getattr(p, "lvl2_pct", 0) or 0),
            "Уровень 2 (начислено), ₽": float(getattr(p, "lvl2_amount_gained", 0) or 0),
            "Использований": int(getattr(p, "times_used", 0) or 0),
            "Создано": getattr(p, "created_at", None),
            "Обновлено": getattr(p, "updated_at", None),
        })

    carts_rows = []
    for c in carts:
        carts_rows.append({
            "Заказ ID": getattr(c, "id", None),
            "Пользователь ID": getattr(c, "user_id", None),
            "Название": getattr(c, "name", None),
            "Сумма товаров, ₽": float(getattr(c, "sum", 0) or 0),
            "Доставка, ₽": float(getattr(c, "delivery_sum", 0) or 0),
            "Доставка (текст)": getattr(c, "delivery_string", None),
            "Комментарий": getattr(c, "commentary", None),
            "Промокод": getattr(c, "promo_code", None),
            "Статус": getattr(c, "status", None),
            "Оплачен": False if bool(getattr(c, "is_active", False)) else True,
            "Создано": getattr(c, "created_at", None),
            "Обновлено": getattr(c, "updated_at", None),
        })

    promos_df = pd.DataFrame(promos_rows)
    carts_df = pd.DataFrame(carts_rows)

    if not carts_df.empty and "Промокод" in carts_df.columns:
        applied = carts_df[
            carts_df["Промокод"].notna() &
            (carts_df["Промокод"].astype(str).str.strip() != "")
            ].copy()
    else:
        applied = pd.DataFrame(columns=carts_df.columns if not carts_df.empty else ["Промокод"])

    if applied.empty:
        summary_df = pd.DataFrame(columns=[
            "Промокод", "Заказов", "Неоплаченных заказов",
            "Сумма товаров итого, ₽", "Средняя сумма, ₽", "Доставка итого, ₽",
        ])
    else:
        applied["Сумма товаров, ₽"] = pd.to_numeric(applied["Сумма товаров, ₽"], errors="coerce").fillna(0.0)
        applied["Доставка, ₽"] = pd.to_numeric(applied["Доставка, ₽"], errors="coerce").fillna(0.0)

        g = applied.groupby("Промокод", as_index=False)
        summary_df = g.agg(
            **{
                "Заказов": ("Заказ ID", "count"),
                "Оплаченных заказов": ("Оплачен", "sum"),
                "Сумма товаров итого, ₽": ("Сумма товаров, ₽", "sum"),
                "Средняя сумма, ₽": ("Сумма товаров, ₽", "mean"),
                "Доставка итого, ₽": ("Доставка, ₽", "sum"),
            }
        )

        summary_df["Сумма товаров итого, ₽"] = summary_df["Сумма товаров итого, ₽"].round(2)
        summary_df["Средняя сумма, ₽"] = summary_df["Средняя сумма, ₽"].round(2)
        summary_df["Доставка итого, ₽"] = summary_df["Доставка итого, ₽"].round(2)
        summary_df = summary_df.sort_values(by=["Заказов", "Промокод"], ascending=[False, True])

    # ✅ Excel-safe datetimes (timezone-naive etc.)
    promos_df = make_excel_safe(promos_df)
    carts_df = make_excel_safe(carts_df)
    summary_df = make_excel_safe(summary_df)

    # 4) Write Excel (3 sheets) + basic styling
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    path = f"/tmp/statistics_{ts}.xlsx"

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        summary_df.to_excel(writer, index=False, sheet_name="Сводка по промокодам")
        promos_df.to_excel(writer, index=False, sheet_name="Промокоды")
        carts_df.to_excel(writer, index=False, sheet_name="Заказы")

        wb = writer.book
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            ws.freeze_panes = "A2"
            if ws.max_row >= 1:
                for cell in ws[1]:
                    cell.font = cell.font.copy(bold=True)

            for col in ws.columns:
                max_len = 0
                col_letter = col[0].column_letter
                for cell in col:
                    v = cell.value
                    if v is None:
                        continue
                    s = str(v)
                    if len(s) > max_len:
                        max_len = len(s)
                ws.column_dimensions[col_letter].width = min(max(10, max_len + 2), 55)

            money_cols = {
                "Сумма товаров, ₽", "Доставка, ₽", "Начислено владельцу, ₽",
                "Уровень 1 (начислено), ₽", "Уровень 2 (начислено), ₽",
                "Сумма товаров итого, ₽", "Средняя сумма, ₽", "Доставка итого, ₽",
            }

            header_map = {}
            for j in range(1, ws.max_column + 1):
                header_map[ws.cell(row=1, column=j).value] = j

            for name in money_cols:
                j = header_map.get(name)
                if not j:
                    continue
                for i in range(2, ws.max_row + 1):
                    ws.cell(row=i, column=j).number_format = "#,##0.00"

            pct_cols = {
                "Скидка, %", "Процент владельца, %", "Уровень 1 (процент), %", "Уровень 2 (процент), %",
            }
            for name in pct_cols:
                j = header_map.get(name)
                if not j:
                    continue
                for i in range(2, ws.max_row + 1):
                    ws.cell(row=i, column=j).number_format = "0.00"

    await message.answer_document(
        FSInputFile(path),
        caption=f"📊 Статистика (Excel)\nСформировано: {ts.replace('_', ' ')}",
    )

    try:
        os.remove(path)
    except Exception:
        pass

@professor_admin_router.message(CommandStart())
@new_admin_router.message(CommandStart(), lambda message: message.from_user.id in OWNER_TG_IDS)
@dose_admin_router.message(CommandStart(), lambda message: message.from_user.id in OWNER_TG_IDS)
async def handle_admin_start(message: Message):
    await message.answer(f'{message.from_user.full_name}, Добро пожаловать в <b>админ панель</b>\n\nВыберите действие кнопками ниже', reply_markup=admin_keyboards.main_menu, parse_mode="html")
    await message.delete()

@professor_admin_router.message(Command('block'), lambda message: message.from_user.id in OWNER_TG_IDS)
@new_admin_router.message(Command('block'), lambda message: message.from_user.id in OWNER_TG_IDS)
@dose_admin_router.message(Command('block'), lambda message: message.from_user.id in OWNER_TG_IDS)
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

@professor_admin_router.message(Command('unblock'), lambda message: message.from_user.id in OWNER_TG_IDS)
@new_admin_router.message(Command('unblock'), lambda message: message.from_user.id in OWNER_TG_IDS)
@dose_admin_router.message(Command('unblock'), lambda message: message.from_user.id in OWNER_TG_IDS)
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

@professor_admin_router.message(admin_states.MainMenu.spends_time, lambda message: message.from_user.id in OWNER_TG_IDS)
@new_admin_router.message(admin_states.MainMenu.spends_time, lambda message: message.from_user.id in OWNER_TG_IDS)
@dose_admin_router.message(admin_states.MainMenu.spends_time, lambda message: message.from_user.id in OWNER_TG_IDS)
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

@professor_admin_router.callback_query(lambda call: call.data.startswith("admin") and call.from_user.id in OWNER_TG_IDS)
@new_admin_router.callback_query(lambda call: call.data.startswith("admin") and call.from_user.id in OWNER_TG_IDS)
@dose_admin_router.callback_query(lambda call: call.data.startswith("admin") and call.from_user.id in OWNER_TG_IDS)
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
    if bot_id == PROFESSOR_BOT_TOKEN.split(":")[0]:
        bot = "professor"
    elif bot_id == DOSE_BOT_TOKEN.split(":")[0]:
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
