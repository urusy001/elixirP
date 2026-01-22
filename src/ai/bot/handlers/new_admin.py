import os
import uuid
import pandas as pd

from typing import Literal, get_args
from datetime import datetime, timedelta
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, FSInputFile, InlineQuery, InlineQueryResultArticle, InputTextMessageContent

from config import ADMIN_TG_IDS, MOSCOW_TZ
from src.ai.bot.texts import admin_texts
from src.ai.bot.handlers import new_admin_router
from src.ai.bot.keyboards import admin_keyboards
from src.helpers import make_excel_safe
from src.tg_methods import get_user_id_by_phone, normalize_phone
from src.webapp import get_session
from src.webapp.crud import get_carts, list_promos, upsert_user, update_user, get_user, get_users
from src.webapp.crud.search import search_users
from src.webapp.schemas import UserCreate, UserUpdate

new_admin_router.inline_query.filter(lambda query: query.from_user.id in ADMIN_TG_IDS)

@new_admin_router.message(CommandStart())
async def handle_start(message: Message):
    await message.answer(admin_texts.greeting, reply_markup=admin_keyboards.admin_menu)

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
            "Оплачен": False if bool(getattr(c, "is_active", False)) else True,
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

@new_admin_router.callback_query()
async def handle_new_admin_callback(call: CallbackQuery, state: FSMContext):
    data = call.data.removeprefix("admin:").split(':')
    state_data = await state.get_data()
    if data[0] == "users":
        if data[1] == "search": await call.message.edit_text(admin_texts.search_users_choice, reply_markup=admin_keyboards.search_users_choice)

    elif data[0] == "spends":
        from .admin import handle_admin_callback
        await handle_admin_callback(call, state)

@new_admin_router.inline_query()
async def handle_inline_query(inline_query: InlineQuery, state: FSMContext):
    data = inline_query.query.strip().split(':')
    if data[0] == "search_user":
        column_name = data[1]
        value = data[2]
        allowed_column_names = Literal["full_name", "username", "email", "tg_id", "phone"]
        if column_name not in get_args(allowed_column_names): results = [InlineQueryResultArticle(id=str(uuid.uuid4()), title=f"Неверный поисковой параметр: {column_name}", input_message_content=InputTextMessageContent(message_text="/start", parse_mode=None), description=f"Позволено: {', '.join(allowed_column_names)}", )]
        elif not value.strip(): results = [InlineQueryResultArticle(id=str(uuid.uuid4()), title=f"Введите поисковый запрос", input_message_content=InputTextMessageContent(message_text="/start", parse_mode=None), description=f"Не трогайте ничего после двоеточия", )]
        else:
            async with get_session() as session: rows, total = await search_users(session, column_name, value, limit=50)
            results = [InlineQueryResultArticle(thumbnail_url=row.photo_url, id=str(uuid.uuid4()), title=row.full_name, description=row.contact_info, input_message_content=InputTextMessageContent(message_text=f"/get_user {row.tg_id}", parse_mode=None)) for row in rows]

        await inline_query.answer(results)
