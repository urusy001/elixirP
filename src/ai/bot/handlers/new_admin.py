import os
import uuid
import pandas as pd

from typing import Literal, get_args
from datetime import datetime, timedelta
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, FSInputFile, InlineQuery, InlineQueryResultArticle, InputTextMessageContent

from config import MOSCOW_TZ, ELIXIR_CHAT_ID
from src.ai.bot.texts import admin_texts
from src.ai.bot.handlers import new_admin_router
from src.ai.bot.keyboards import admin_keyboards
from src.ai.bot.states import admin_states
from src.helpers import make_excel_safe, user_carts_analytics_text, cart_analysis_text
from src.tg_methods import get_user_id_by_phone, normalize_phone, get_user_id_by_username
from src.webapp import get_session
from src.webapp.crud import get_carts, list_promos, upsert_user, update_user, get_user, get_user_usage_totals, get_user_carts, get_carts_by_date, get_cart_by_id
from src.webapp.crud.search import search_users, search_carts
from src.webapp.models import Cart
from src.webapp.schemas import UserCreate, UserUpdate


@new_admin_router.message(CommandStart(deep_link=True))
async def handle_deep_start(message: Message, command: CommandObject, state: FSMContext):
    print(command, command.args or 131111)


@new_admin_router.message(CommandStart())
async def handle_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(admin_texts.greeting, reply_markup=admin_keyboards.main_menu)
    await message.delete()

@new_admin_router.message(Command('edit_and_pin'), lambda message: message.reply_to_message)
async def handle_pin(message: Message):
    forwarded_message = message.reply_to_message
    c_id = forwarded_message.forward_from_chat.id
    m_id = forwarded_message.forward_from_message_id
    await message.bot.edit_message_reply_markup(message_id=m_id,  chat_id=c_id, reply_markup=admin_keyboards.open_test)

@new_admin_router.message(Command('set_premium'))
async def add_premium(message: Message):
    phone = message.text.removeprefix("/set_premium ").strip()
    if phone:
        phone = normalize_phone(phone)
        async with get_session() as session: user = await get_user(session, 'tg_phone', phone)
        user_id = await get_user_id_by_phone(phone) if not (user and user.tg_id) else user.tg_id
        if not user_id: return await message.answer('Пользователь не найден по номеру в ТГ')

    else: return await message.answer('Ошибка команды: <code>/set_premium номер_в_тг</code>')
    async with get_session() as session: user = await update_user(session, int(user_id), UserUpdate(premium_until=datetime.now(tz=MOSCOW_TZ) + timedelta(weeks=1044)))
    if user: return await message.answer(f'Пользователю с номером {user.tg_phone} выдан премиум доступ')
    else:
        async with get_session() as session: user = await upsert_user(session, UserCreate(tg_phone=phone, tg_id=user_id, premium_until=datetime.now(tz=MOSCOW_TZ) + timedelta(weeks=1044)))
        if user: await message.answer(f'Пользователю с номером {user.tg_phone} выдан премиум доступ')
        else: await message.answer("Ошибка команды: пользователь не пользовался ботом или не был найден в базе")
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
            "Оплачен": False if not bool(getattr(c, "is_paid", False)) else True,
            "Создано": getattr(c, "created_at", None),
            "Обновлено": getattr(c, "updated_at", None),
        })

    promos_df = pd.DataFrame(promos_rows)
    carts_df = pd.DataFrame(carts_rows)
    if not carts_df.empty and "Промокод" in carts_df.columns: applied = carts_df[carts_df["Промокод"].notna() & (carts_df["Промокод"].astype(str).str.strip() != "")].copy()
    else: applied = pd.DataFrame(columns=carts_df.columns if not carts_df.empty else ["Промокод"])

    if applied.empty: summary_df = pd.DataFrame(columns=["Промокод", "Заказов", "Неоплаченных заказов", "Сумма товаров итого, ₽", "Средняя сумма, ₽", "Доставка итого, ₽"])
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

    promos_df = make_excel_safe(promos_df)
    carts_df = make_excel_safe(carts_df)
    summary_df = make_excel_safe(summary_df)
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
                for cell in ws[1]: cell.font = cell.font.copy(bold=True)

            for col in ws.columns:
                max_len = 0
                col_letter = col[0].column_letter
                for cell in col:
                    v = cell.value
                    if v is None: continue
                    s = str(v)
                    if len(s) > max_len: max_len = len(s)
                ws.column_dimensions[col_letter].width = min(max(10, max_len + 2), 55)

            money_cols = {
                "Сумма товаров, ₽", "Доставка, ₽", "Начислено владельцу, ₽",
                "Уровень 1 (начислено), ₽", "Уровень 2 (начислено), ₽",
                "Сумма товаров итого, ₽", "Средняя сумма, ₽", "Доставка итого, ₽",
            }

            header_map = {}
            for j in range(1, ws.max_column + 1): header_map[ws.cell(row=1, column=j).value] = j
            for name in money_cols:
                j = header_map.get(name)
                if not j: continue
                for i in range(2, ws.max_row + 1): ws.cell(row=i, column=j).number_format = "#,##0.00"

            pct_cols = {
                "Скидка, %", "Процент владельца, %", "Уровень 1 (процент), %", "Уровень 2 (процент), %",
            }
            for name in pct_cols:
                j = header_map.get(name)
                if not j: continue
                for i in range(2, ws.max_row + 1): ws.cell(row=i, column=j).number_format = "0.00"

    await message.answer_document(FSInputFile(path), caption=f"📊 Статистика (Excel)\nСформировано: {ts.replace('_', ' ')}")
    try: os.remove(path)
    except Exception: pass

@new_admin_router.message(Command('get_user'))
async def handle_get_user(message: Message):
    user_id = message.text.removeprefix("/get_user ").strip()
    if not user_id or not user_id.isdigit(): await message.answer("Ошибка команды: <code>/get_user айди_тг</code>", reply_markup=admin_keyboards.back)
    else:
        async with get_session() as session:
            user = await get_user(session, 'tg_id', user_id)
            token_usages = await get_user_usage_totals(session, user.tg_id)
            user_carts = [cart for cart in await get_user_carts(session, user.tg_id)]

        paid: list[Cart] = []
        unpaid: list[Cart] = []
        for cart in user_carts: paid.append(cart) if cart.is_paid else unpaid.append(cart)
        totals = token_usages["totals"]
        total_requests = totals["total_requests"]
        total_cost_usd = totals["total_cost_usd"]
        avg_cost_per_request = totals["avg_cost_per_request"]
        total_rub = sum([cart.sum for cart in user_carts])
        paid_rub = sum([cart.sum for cart in paid])
        unpaid_rub = sum([cart.sum for cart in unpaid])
        is_member = False
        try: is_member = await message.bot.get_chat_member(ELIXIR_CHAT_ID, user.tg_id)
        except Exception as e: print(e)
        user_text = (f"👤 <b>{user.full_name}</b>\n"
                     f"📞 Номер ТГ: <i>{user.tg_phone}</i>\n"
                     f"🆔 Айди ТГ: <i>{user.tg_id}</i>\n"
                     f"📲 Последняя контактная информация в заказах:\n"
                     f"{user.phone} {user.email}\n"
                     f"📣 Состоит в чате: <i>{'❌ Нет' if not is_member else '✅ Да'}</i>\n\n"
                     f"🛍️ <b>Заказов: {len(user_carts)} на сумму {total_rub}₽\n</b>"
                     f" — Оплаченных: <i>{len(paid)} на сумму {paid_rub}₽</i>\n"
                     f" — Неоплаченных: <i>{len(unpaid)} на сумму {unpaid_rub}₽</i>\n\n"
                     f"🤖 <b>Запросов ИИ: {total_requests} на сумму {total_cost_usd}$</b>\n"
                     f"💲 Стоимость запроса в среднем: <i>{avg_cost_per_request}</i>")

        if user.blocked_until and user.blocked_until > datetime.now(MOSCOW_TZ): user_text += f"\n\n‼️ <b>ЗАБЛОКИРОВАН ДО {user.blocked_until.date()} {user.blocked_until.hour}:{user.blocked_until.minute} по МСК ‼️</b>"
        await message.answer(user_text, reply_markup=admin_keyboards.view_user_menu(user.tg_id, len(user_carts), bool(user.blocked_until and user.blocked_until > datetime.now(MOSCOW_TZ))))

@new_admin_router.message(admin_states.ViewUser.block_days, lambda message: message.text.isdigit())
async def handle_block_days(message: Message, state: FSMContext):
    state_data = await state.get_data()
    user_id = state_data["user_id"]
    days = int(message.text.strip())
    if days == 0: until = datetime.max.replace(tzinfo=MOSCOW_TZ)
    else: until = datetime.now() + timedelta(days=abs(int(days)))
    async with get_session() as session: user = await update_user(session, user_id, UserUpdate(blocked_until=until))
    await message.answer(f"Пользователь {user.full_name} {user.tg_phone} <b>успешно заблокирован до {until.date()} {until.hour}:{until.minute} по МСК</b>", reply_markup=admin_keyboards.back_to_user(user.tg_id))

@new_admin_router.message(Command("get_cart"))
async def handle_get_cart(message: Message, state: FSMContext):
    cart_id = message.text.removeprefix("/get_cart").strip()
    if not cart_id.isdigit(): await message.answer("Ошибка команды: <code>/get_cart номер_заказа</code>", reply_markup=admin_keyboards.back)
    else:
        async with get_session() as session: cart = await get_cart_by_id(session, int(cart_id))
        if cart: await message.answer(await cart_analysis_text(session, int(cart_id)), reply_markup=admin_keyboards.back_to_user(cart.user_id))
        else:
            await message.answer(f"Заказ по номеру {cart_id} не существует")
            await handle_start(message, state)

@new_admin_router.callback_query()
async def handle_new_admin_callback(call: CallbackQuery, state: FSMContext):
    data = call.data.removeprefix("admin:").split(':')
    state_data = await state.get_data()
    if data[0] == "users":
        if data[1] == "search": await call.message.edit_text(admin_texts.search_users_choice, reply_markup=admin_keyboards.search_users_choice)
        elif data[1].isdigit():
            user_id = int(data[1])
            async with get_session() as session: user = await get_user(session, 'tg_id', user_id)
            if data[2] == "carts":
                async with get_session() as session: analysis_text = await user_carts_analytics_text(session, user_id)
                await call.message.edit_text(f"{call.message.html_text.splitlines()[0]}\n{analysis_text}")

            elif data[2] == "block":
                await call.message.edit_text(admin_texts.block_days, reply_markup=admin_keyboards.back)
                await state.set_state(admin_states.ViewUser.block_days)
                await state.update_data(user_id=user.tg_id)

            elif data[2] == "unblock":
                async with get_session() as session: user = await update_user(session, user.tg_id, UserUpdate(blocked_until=None))
                await call.message.edit_text(f"Пользователь {user.full_name} {user.tg_phone} успешно <b>разблокирован 🔓</b>", reply_markup=admin_keyboards.back_to_user(user.tg_id))

    elif data[0] == "spends":
        from .admin import handle_admin_callback
        await handle_admin_callback(call, state)

    elif data[0] == "main_menu": await handle_start(call.message, state)
    elif data[0] == "main_menuu":
        await call.message.answer(admin_texts.greeting, reply_markup=admin_keyboards.admin_menu)
        await state.clear()


@new_admin_router.inline_query()
async def handle_inline_query(inline_query: InlineQuery, state: FSMContext):
    data = inline_query.query.strip().split(maxsplit=2)
    start_input_content = InputTextMessageContent(message_text="/start", parse_mode=None)
    if data[0] == "search_user" and len(data) == 3:
        column_name = data[1]
        value = data[2]
        allowed_column_names = Literal["full_name", "username", "email", "tg_id", "phone"]
        if column_name not in get_args(allowed_column_names): results = [InlineQueryResultArticle(id=str(uuid.uuid4()), title=f"❌ Неверный поисковой параметр: {column_name}", input_message_content=start_input_content, description=f"Позволено: {', '.join(allowed_column_names)}", )]
        elif not value.strip(): results = [InlineQueryResultArticle(id=str(uuid.uuid4()), title=f"Введите поисковый запрос", input_message_content=start_input_content, description=f"Не трогайте ничего после двоеточия", )]
        elif column_name == "username":
            value = await get_user_id_by_username(value.removeprefix("@"))
            if value:
                column_name = "tg_id"
                async with get_session() as session: rows, total = await search_users(session, column_name, value, limit=50)
                if rows: results = [InlineQueryResultArticle(thumbnail_url=row.photo_url, id=str(uuid.uuid4()), title=row.full_name, description=row.contact_info, input_message_content=InputTextMessageContent(message_text=f"/get_user {row.tg_id}", parse_mode=None)) for row in rows]
                else: results = [InlineQueryResultArticle(id=str(uuid.uuid4()), title="В баночке не найдено пользователей по поисковому запросу 🫙", description="Попробуйте другой запрос", input_message_content=start_input_content)]

            else: results = [InlineQueryResultArticle(id=str(uuid.uuid4()), title="Пользователя с таким username не существует", input_message_content=start_input_content)]

        else:
            async with get_session() as session: rows, total = await search_users(session, column_name, value, limit=50)
            if rows: results = [InlineQueryResultArticle(thumbnail_url=row.photo_url, id=str(uuid.uuid4()), title=row.full_name, description=row.contact_info, input_message_content=InputTextMessageContent(message_text=f"/get_user {row.tg_id}", parse_mode=None)) for row in rows]
            else: results = [InlineQueryResultArticle(id=str(uuid.uuid4()), title="В баночке не найдено пользователей по поисковому запросу 🫙", description="Попробуйте другой запрос", input_message_content=start_input_content)]

    elif data[0] == "search_cart":
        value = data[1]
        if not value.isdigit():
            date_parts = value.split(".")
            if len(date_parts) == 3:
                day = date_parts[0]
                month = date_parts[1]
                year = date_parts[2]
                if not all((x.isdigit() for x in [day, month, year])): results = [InlineQueryResultArticle(id=str(uuid.uuid4()), title="Введенный запрос не число и не дата", description="Поиск заказов возможен только по их номерам или дате (дд.мм.гггг)", input_message_content=start_input_content)]
                else:
                    dt = datetime(year=int(year), month=int(month), day=int(day), tzinfo=MOSCOW_TZ)
                    async with get_session() as session: carts = await get_carts_by_date(session, dt)
                    if carts: results = [InlineQueryResultArticle(id=str(uuid.uuid4()), title=f"{cart.name} от {cart.user.full_name}", description=f"Статус: {cart.status}, Обновлено: {cart.updated_at.hour}:{cart.updated_at.minute}, {cart.updated_at.date()}", input_message_content=InputTextMessageContent(message_text=f"/get_cart {cart.id}")) for cart in carts]
                    else: results = [InlineQueryResultArticle(id=str(uuid.uuid4()), title="В баночке не найдено заказов по поисковому запросу 🫙", description="Попробуйте другой запрос", input_message_content=start_input_content)]

            else: results = [InlineQueryResultArticle(id=str(uuid.uuid4()), title="Введенный запрос не число и не дата", description="Поиск заказов возможен только по их номерам или дате (дд.мм.гггг)", input_message_content=start_input_content)]
        else:
            cart_id = int(value)
            async with get_session() as session: carts, total = await search_carts(session, cart_id, limit=50)
            if carts: results = [InlineQueryResultArticle(id=str(uuid.uuid4()), title=f"{cart.name} от {cart.user.full_name}", description=f"Статус: {cart.status}, Обновлено: {cart.updated_at.hour}:{cart.updated_at.minute}, {cart.updated_at.date()}", input_message_content=InputTextMessageContent(message_text=f"/get_cart {cart.id}")) for cart in carts]
            else: results = [InlineQueryResultArticle(id=str(uuid.uuid4()), title="В баночке не найдено заказов по поисковому запросу 🫙", description="Попробуйте другой запрос", input_message_content=start_input_content)]

    else: results = []
    await inline_query.answer(results)
