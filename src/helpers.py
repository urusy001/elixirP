from __future__ import annotations

import asyncio
import hashlib
import hmac
import html
import json
import random
import re
import time
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from functools import wraps
from logging import Logger
from typing import Any
from typing import Optional
from urllib.parse import parse_qsl

import pandas as pd
from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from aiogram.types import Message, CallbackQuery
from bs4 import BeautifulSoup, Tag
from fastapi import HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import BigInteger, Integer, String, DateTime, Numeric, Boolean, select, distinct, func, desc, case
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy.orm.attributes import InstrumentedAttribute
from transliterate import translit

from config import ELIXIR_CHAT_ID, NEW_BOT_TOKEN, INTERNAL_API_TOKEN, MOSCOW_TZ
from src.ai.bot.texts import user_texts
from src.webapp import get_session
from src.webapp.models import Cart, CartItem, TgCategory, Feature, Product
from src.webapp.models.product_tg_categories import product_tg_categories
from src.webapp.models.user import User

MAX_TG_MSG_LEN = 4096
_NULLY = {None, "", "null", "None", "NULL"}
ALLOWED_TAGS = {
    "b", "strong",
    "i", "em",
    "u", "ins",
    "s", "strike", "del",
    "span", "tg-spoiler",
    "a",
    "tg-emoji",
    "code", "pre",
    "blockquote",
}
_csv_lock = asyncio.Lock()  # чтобы несколько хендлеров не писали одновременно
def _s(obj, attr: str, default: str = "") -> str:
    v = getattr(obj, attr, None)
    if v is None:
        return default
    return str(v)
def with_typing(func):
    """
    Decorator that sends 'typing...' action while the wrapped handler is running.
    Automatically detects Bot from handler args.
    """  
    @wraps(func)
    async def wrapper(*args, **kwargs):
        bot: Bot | None = None
        chat_id: int | None = None
        for arg in args:
            if isinstance(arg, Bot): bot = arg
            elif isinstance(arg, Message): chat_id = arg.chat.id

        if not bot: bot = kwargs.get("ai/bot") or kwargs.get("professor_bot")
        if not chat_id:
            if "message" in kwargs: chat_id = kwargs["message"].chat.id

        if not bot or not chat_id: raise ValueError("Could not detect Bot or chat_id for typing decorator")
        async def loop():
            try:
                while True:
                    try: await bot.send_chat_action(chat_id, "typing")
                    except Exception: pass
                    await asyncio.sleep(random.uniform(3, 5))
            except asyncio.CancelledError: return  # exit immediately when cancelled

        task = asyncio.create_task(loop())
        try: return await func(*args, **kwargs)
        finally:
            task.cancel()  # cancel immediately
            try: await task
            except asyncio.CancelledError: pass
    return wrapper
async def split_text(text: str, limit: int = MAX_TG_MSG_LEN) -> list[str]:
    """
    Splits long text into chunks safe for Telegram.
    Tries to split at paragraph or sentence boundaries.
    """
    chunks = []
    while len(text) > limit:
        split_idx = text.rfind("\n", 0, limit)
        if split_idx == -1: split_idx = text.rfind(". ", 0, limit)
        if split_idx == -1: split_idx = limit

        chunks.append(text[:split_idx].strip())
        text = text[split_idx:].strip()
    if text: chunks.append(text)
    return chunks
async def normalize(text: str) -> str:
    try: return translit(text, "ru", reversed=True).lower()
    except Exception: return text.lower()
def _get_user_column(name: str) -> InstrumentedAttribute:
    col = getattr(User, name, None)
    if col is None or not hasattr(col, "type"): raise ValueError(f"Unknown column name for User: {name!r}")
    return col
def _coerce_datetime(value: str) -> datetime:
    """
    Accepts:
      - ISO-8601 (e.g., '2025-11-12T15:23:01+00:00', '2025-11-12 15:23:01')
      - 'Z' suffix (UTC)
      - UNIX epoch seconds (e.g., '1731438181')
    Returns timezone-aware datetime when possible (UTC if epoch or 'Z').
    """
    s = str(value)
    if s.isdigit(): return datetime.fromtimestamp(int(s), tz=timezone.utc)
    if s.endswith("Z"):
        try: return datetime.fromisoformat(s[:-1]).replace(tzinfo=timezone.utc)
        except Exception: pass

    return datetime.fromisoformat(s)
def normalize_user_value(column_name: str, raw_value: Any) -> Any:
    """
    Normalize a raw (string-ish) value to the Python type expected by User.<column_name>.

    Examples:
        normalize_user_value("tg_id", "7792693628") -> int(7792693628)
        normalize_user_value("email", "a@b.com") -> "a@b.com"
        normalize_user_value("blocked_until", "2025-11-12T15:23:01+00:00") -> datetime(...)
        normalize_user_value("blocked_until", "1731438181") -> datetime(..., tzinfo=UTC)

    Raises:
        ValueError for unknown column names or invalid casts.
    """
    col = _get_user_column(column_name)
    col_type = col.type
    is_nullable = getattr(col.expression, "nullable", True)  # fallback True
    if raw_value in _NULLY and is_nullable: return None
    if isinstance(col_type, (Integer, BigInteger)): return int(raw_value)
    if isinstance(col_type, String): return str(raw_value) if raw_value is not None else None
    if isinstance(col_type, DateTime): return _coerce_datetime(raw_value)
    if isinstance(col_type, Numeric): return Decimal(str(raw_value))
    if isinstance(col_type, Boolean):
        s = str(raw_value).strip().lower()
        return s in {"1", "true", "t", "yes", "y", "on"}

    return raw_value


def _fmt(x):
    try:
        if x is None: return "-"
        x = float(x)
        if abs(x) >= 10000: return f"{x:,.0f}".replace(",", " ")
        if abs(x) >= 1000: return f"{x:,.1f}".replace(",", " ")
        if abs(x) >= 100: return f"{x:.1f}"
        if abs(x) >= 10: return f"{x:.2f}"
        if abs(x) >= 1: return f"{x:.2f}"
        return f"{x:.4f}"
    except: return str(x)


def _fmt_int(x):
    try: return str(int(x))
    except: return str(x)


def format_order_for_amocrm(order_number: int | str, payload: dict[str, Any], delivery_service: str, tariff: str | None, commentary_text: str, promocode: str, delivery_sum: float | int | str) -> str:
    """
    Format Telegram checkout payload into AmoCRM-friendly Russian text.

    :param delivery_sum:
    :param promocode:
    :param commentary_text:
    :param order_number: e.g. 12529
    :param payload: checkout JSON dict (your big object from backend)
    :param delivery_service: e.g. "CDEK", "Yandex"
    :param tariff: for CDEK: "pickup_point" | "courier"; for Yandex can be None/ignored
    """
    checkout = payload.get("checkout_data", {}) or {}
    items = checkout.get("items", []) or []
    delivery = payload.get("selected_delivery", {}) or {}
    contact = payload.get("contact_info", {}) or {}
    address_data = delivery.get("address", {}) or {}
    order_date = datetime.now().strftime("%d.%m.%Y")
    lines_items: list[str] = []
    for idx, item in enumerate(items, start=1):
        name = item.get("name", "Товар")
        qty = item.get("qty", 1)
        subtotal = int(item.get("subtotal", 0))
        subtotal_str = f"{subtotal:,}".replace(",", " ")  # 37260 -> "37 260"
        lines_items.append(f"{idx}. {name} {qty}шт. — {subtotal_str}руб.")

    items_block = "\n".join(lines_items) if lines_items else "Товары не указаны."
    delivery_service_norm = (delivery_service or "").strip().upper()
    tariff_norm = (tariff or "").strip().lower() if tariff is not None else ""
    postal_code = address_data.get("postal_code") or ""
    formatted_cdek_addr = address_data.get("formatted") or address_data.get("name")
    yandex_addr = address_data.get("address") or ""
    yandex_name = address_data.get("name") or ""  # for self_pickup PVZ label
    delivery_mode = (delivery.get("deliveryMode") or "").strip()  # for Yandex

    if delivery_service_norm == "CDEK":
        if tariff_norm == "office": prefix = "Доставка: Пункт выдачи СДЕК"
        elif tariff_norm == "door": prefix = "Доставка: Курьер СДЭК"
        else: prefix = "Доставка: СДЭК"

        delivery_line = f"{prefix}: {postal_code}, {formatted_cdek_addr}".strip()

    elif delivery_service_norm == "YANDEX":
        if delivery_mode == "self_pickup":
            base = yandex_addr
            if yandex_name: base = f"{yandex_addr} ({yandex_name})"
            prefix = "Доставка: Пункт выдачи Яндекс"
            delivery_line = f"{prefix}: {base}".strip()

        elif delivery_mode in ("time_interval", "door"):
            prefix = "Доставка: Яндекс до двери"
            delivery_line = f"{prefix}: {yandex_addr}".strip()

        else:
            prefix = "Доставка: Яндекс ПВЗ"
            delivery_line = f"{prefix}: {yandex_addr}".strip()

    else:
        base_addr = formatted_cdek_addr or yandex_addr
        prefix = f"Доставка: {delivery_service}"
        delivery_line = f"{prefix}: {postal_code + ', ' if postal_code else ''}{base_addr}".strip()

    name = contact.get("name") or ""
    surname = contact.get("surname") or ""
    full_name = (surname + " " + name).strip() or "Не указано"
    phone = contact.get("phone") or "Не указан"
    email = contact.get("email") or "Не указан"

    text = (
        f"Заказ №{order_number} с Магазина Телеграм\n"
        f"Дата заказа: {order_date}\n"
        f"Cостав заказа:\n"
        f"{items_block}\n\n"
        f"{delivery_line}\n"
        f"Стоимость доставки: {delivery_sum}\n\n"
        f"Имя клиента: {full_name}\n"
        f"Номер телефона: {phone}\n"
        f"Email: {email}\n\n"
        f"Промо-код: {promocode}\n"
        f"Комментарий к заказу: {commentary_text}"
    )

    return text

def normalize_address_for_cf(address: object) -> str | None:
    if not address: return None
    if isinstance(address, str): s = address
    elif isinstance(address, dict):
        postal_code = address.get("postal_code")
        city = address.get("city")
        region = address.get("region")
        country_code = address.get("country_code")
        line = address.get("address") or address.get("name")
        parts = [p for p in [postal_code, city, region, country_code, line] if p]
        s = ", ".join(map(str, parts))
    else: s = str(address)
    if len(s) > 255: s = s[:255]
    return s or None


def normalize_html_for_telegram(raw_html: str) -> str:
    """
    Превращает произвольный HTML в валидный HTML для Telegram (parse_mode='HTML').

    Делает:
    - h1–h6 -> <b>
    - p -> текст + два переноса
    - br -> \n
    - ul/ol/li -> буллеты "• ..."
    - убирает article/div/span без tg-spoiler и прочие контейнеры
    - оставляет только допустимые теги и нужные атрибуты
    - декодирует HTML-сущности (&nbsp; &mdash; ...) в юникод и заново экранирует
    """
    raw_html = html.unescape(raw_html)
    soup = BeautifulSoup(raw_html, "html.parser")
    for tag in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]): tag.name = "b"
    for lst in soup.find_all(["ul", "ol"]):
        lines = []
        for li in lst.find_all("li", recursive=False):
            text = li.get_text(" ", strip=True)
            if text: lines.append(f"• {text}")
        lst.replace_with("\n".join(lines))

    for br in soup.find_all("br"): br.replace_with("\n")
    for p in soup.find_all("p"):
        text = p.get_text(" ", strip=True)
        if text: p.replace_with(text + "\n")
        else: p.decompose()

    for tag in list(soup.find_all(True)):  # True = любой тег
        if not isinstance(tag, Tag): continue
        name = tag.name
        if name not in ALLOWED_TAGS:
            tag.unwrap()
            continue

        if name == "span":
            classes = tag.get("class", [])
            if "tg-spoiler" in classes: tag.attrs = {"class": "tg-spoiler"}
            else: tag.unwrap()

        elif name == "a":
            href = tag.get("href")
            if href: tag.attrs = {"href": href}
            else: tag.unwrap()

        elif name == "tg-emoji":
            emoji_id = tag.get("emoji-id")
            if emoji_id: tag.attrs = {"emoji-id": emoji_id}
            else: tag.unwrap()

        elif name == "code":
            if isinstance(tag.parent, Tag) and tag.parent.name == "pre":
                cls = tag.get("class")
                if cls: tag.attrs = {"class": cls}
                else: tag.attrs = {}
            else: tag.attrs = {}

        elif name == "pre": tag.attrs = {}
        elif name == "blockquote":
            if "expandable" in tag.attrs: tag.attrs = {"expandable": None}  # <blockquote expandable>
            else: tag.attrs = {}

        else: tag.attrs = {}

    text = str(soup)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = "\n".join(line.rstrip() for line in text.splitlines())
    return text.strip()


async def _notify_user(message: Message, text: str, timer: float | None = None, logger: Logger = None) -> None:
    if logger: logger.info("Notify user %s | text_preview=%r | timer=%s", message.from_user.id, text[:100], timer)
    x = await message.answer(text, parse_mode="HTML")
    if timer:
        await asyncio.sleep(timer)
        await x.delete()
        if logger: logger.debug("Deleted notification message for user %s", message.from_user.id)


async def CHAT_NOT_BANNED_FILTER(obj: Message | CallbackQuery) -> bool:
    try:
        user_id = obj.from_user.id
        bot = obj.bot
        member = await bot.get_chat_member(ELIXIR_CHAT_ID, user_id)
        if member.status in [ChatMemberStatus.KICKED]:
            await bot.send_message(user_id, user_texts.banned_in_channel)
            return False
        else: return True
    except: return True

async def CHAT_ADMIN_REPLY_FILTER(message: Message, bot: Bot) -> bool:
    if getattr(message.chat, "id") not in [ELIXIR_CHAT_ID]: return False
    elif not message.reply_to_message: return False
    if message.sender_chat and message.sender_chat.id == message.chat.id: return True
    if message.from_user:
        member = await bot.get_chat_member(message.chat.id, message.from_user.id)
        return member.status in ("administrator", "creator")

    return False

class TelegramAuthPayload(BaseModel): initData: str
class TelegramInitDataError(Exception): """Base error for init data validation issues."""
class TelegramInitDataSignatureError(TelegramInitDataError): """Signature does not match, init data is not trusted."""
class TelegramInitDataExpiredError(TelegramInitDataError): """auth_date is too old."""

def validate_init_data(init_data: str, bot_token: str = NEW_BOT_TOKEN, max_age_seconds: int = 60*60*2) -> dict[str, Any]:
    """
    Validate Telegram Mini App init data according to the official algorithm.

    :param init_data: Raw query string from Telegram (window.Telegram.WebApp.initData).
    :param bot_token: Your bot token (from BotFather).
    :param max_age_seconds: Max allowed age for auth_date (0 to skip this check).
    :return: dict with parsed parameters (user, query_id, auth_date, etc.).
    :raises TelegramInitDataError: On invalid or expired data.
    """
    params_list = parse_qsl(init_data, keep_blank_values=True)
    params: dict[str, str] = {}
    received_hash: Optional[str] = None

    for key, value in params_list:
        if key == "hash": received_hash = value
        else: params[key] = value

    if received_hash is None: raise TelegramInitDataSignatureError("Missing 'hash' parameter in init data.")

    data_check_string_parts = [f"{k}={v}" for k, v in sorted(params.items(), key=lambda kv: kv[0])]
    data_check_string = "\n".join(data_check_string_parts)
    secret_key = hmac.new(
        key=b"WebAppData",
        msg=bot_token.encode("utf-8"),
        digestmod=hashlib.sha256
    ).digest()  # IMPORTANT: keep as raw bytes
    check_hash = hmac.new(
        key=secret_key,
        msg=data_check_string.encode("utf-8"),
        digestmod=hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(check_hash, received_hash): raise TelegramInitDataSignatureError("Init data signature mismatch.")
    if "auth_date" in params and max_age_seconds > 0:
        try: auth_date = int(params["auth_date"])
        except ValueError: raise TelegramInitDataError("Invalid auth_date format.")

        now = int(time.time())
        if now - auth_date > max_age_seconds: raise TelegramInitDataExpiredError("Init data is too old.")

    result: dict[str, Any] = dict(params)

    if "user" in result:
        try: result["user"] = json.loads(result["user"])
        except json.JSONDecodeError: pass

    return result


def require_internal_token(req: Request) -> None:
    expected = INTERNAL_API_TOKEN
    got = req.headers.get("X-Internal-Token")
    if not expected or got != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")

async def check_blocked(message: Message):
    tg_id = int(message.from_user.id)
    async with get_session() as session:
        stmt = select(User).where(User.tg_id == tg_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

    if user and user.blocked_until and user.blocked_until.replace(tzinfo=MOSCOW_TZ) > datetime.now(MOSCOW_TZ):
        await message.answer(user_texts.banned_until.replace("name", message.from_user.full_name).replace("date", f'{user.blocked_until.date()}').replace("Блокировка до 9999-12-31, п", "П"))
        return False
    return True

def make_excel_safe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    tz_cols = df.select_dtypes(include=["datetimetz"]).columns
    for c in tz_cols: df[c] = df[c].dt.tz_localize(None)
    for c in df.columns:
        if df[c].dtype == "object": df[c] = df[c].apply(lambda x: x.replace(tzinfo=None) if hasattr(x, "tzinfo") and x.tzinfo else x)
    return df


def _fmt_dt(dt: datetime | None) -> str:
    if not dt: return "—"
    return dt.strftime("%Y-%m-%d %H:%M")

def _money(x: Any) -> Decimal:
    if x is None: return Decimal("0")
    if isinstance(x, Decimal): return x
    return Decimal(str(x))

async def user_carts_analytics_text(db: AsyncSession, user_id: int, *, days: int = 30, top_n: int = 5, recent_n: int = 8) -> str:
    since_dt = datetime.now(timezone.utc) - timedelta(days=days)

    totals_stmt = (
        select(
            func.count(Cart.id).label("carts_total"),
            func.coalesce(func.sum(Cart.sum), 0).label("sum_total"),
            func.coalesce(func.sum(Cart.delivery_sum), 0).label("delivery_sum_total"),
            func.coalesce(func.sum(Cart.promo_gains), 0).label("promo_gains_total"),
            func.sum(case((Cart.is_paid.is_(True), 1), else_=0)).label("paid_cnt"),
            func.sum(case((Cart.is_paid.is_(False), 1), else_=0)).label("unpaid_cnt"),
            func.sum(case((Cart.is_active.is_(True), 1), else_=0)).label("active_cnt"),
            func.sum(case((Cart.is_active.is_(False), 1), else_=0)).label("inactive_cnt"),
            func.sum(case((Cart.is_canceled.is_(True), 1), else_=0)).label("canceled_cnt"),
            func.sum(case((Cart.is_shipped.is_(True), 1), else_=0)).label("shipped_cnt"),
            func.sum(case((Cart.promo_code.isnot(None), 1), else_=0)).label("with_promo_cnt"),
            func.max(Cart.created_at).label("last_cart_at"),
            func.min(Cart.created_at).label("first_cart_at"),
            func.sum(case((Cart.created_at >= since_dt, 1), else_=0)).label("carts_last_days_cnt"),
        )
        .where(Cart.user_id == user_id)
    )
    t = (await db.execute(totals_stmt)).one()

    carts_total = int(t.carts_total or 0)
    sum_total = _money(t.sum_total)
    delivery_total = _money(t.delivery_sum_total)
    promo_total = _money(t.promo_gains_total)
    avg_sum = (sum_total / carts_total) if carts_total else Decimal("0")

    status_rows = (await db.execute(
        select(Cart.status, func.count(Cart.id).label("cnt"))
        .where(Cart.user_id == user_id)
        .group_by(Cart.status)
        .order_by(desc("cnt"))
    )).all()

    it = (await db.execute(
        select(
            func.count(CartItem.id).label("lines_total"),
            func.coalesce(func.sum(CartItem.quantity), 0).label("qty_total"),
            func.count(distinct(CartItem.product_onec_id)).label("products_distinct"),
            func.count(distinct(CartItem.feature_onec_id)).label("positions_distinct"),
        )
        .select_from(CartItem)
        .join(Cart, Cart.id == CartItem.cart_id)
        .where(Cart.user_id == user_id)
    )).one()

    # ✅ Топ позиций: Product.name + граммовка (Feature.name) + product_onec_id
    top_positions_rows = (await db.execute(
        select(
            CartItem.product_onec_id.label("product_id"),
            Product.name.label("product_name"),
            CartItem.feature_onec_id.label("feature_id"),
            Feature.name.label("feature_name"),
            func.sum(CartItem.quantity).label("qty"),
            func.coalesce(func.sum(CartItem.quantity * func.coalesce(Feature.price, 0)), 0).label("rev"),
        )
        .select_from(CartItem)
        .join(Cart, Cart.id == CartItem.cart_id)
        .outerjoin(Feature, Feature.onec_id == CartItem.feature_onec_id)
        .outerjoin(Product, Product.onec_id == CartItem.product_onec_id)
        .where(Cart.user_id == user_id)
        .group_by(CartItem.product_onec_id, Product.name, CartItem.feature_onec_id, Feature.name)
        .order_by(desc("qty"))
        .limit(top_n)
    )).all()

    # TG категории
    cat_rows = (await db.execute(
        select(
            TgCategory.id.label("cat_id"),
            TgCategory.name.label("cat_name"),
            func.sum(CartItem.quantity).label("qty"),
            func.coalesce(func.sum(CartItem.quantity * func.coalesce(Feature.price, 0)), 0).label("rev"),
            func.count(distinct(CartItem.product_onec_id)).label("products_distinct"),
        )
        .select_from(CartItem)
        .join(Cart, Cart.id == CartItem.cart_id)
        .join(product_tg_categories, product_tg_categories.c.product_onec_id == CartItem.product_onec_id)
        .join(TgCategory, TgCategory.id == product_tg_categories.c.tg_category_id)
        .outerjoin(Feature, Feature.onec_id == CartItem.feature_onec_id)
        .where(Cart.user_id == user_id)
        .group_by(TgCategory.id, TgCategory.name)
        .order_by(desc("qty"))
        .limit(top_n)
    )).all()

    cats_distinct = (await db.execute(
        select(func.count(distinct(product_tg_categories.c.tg_category_id)))
        .select_from(CartItem)
        .join(Cart, Cart.id == CartItem.cart_id)
        .join(product_tg_categories, product_tg_categories.c.product_onec_id == CartItem.product_onec_id)
        .where(Cart.user_id == user_id)
    )).scalar_one() or 0

    recent_rows = (await db.execute(
        select(
            Cart.id,
            Cart.created_at,
            Cart.sum,
            Cart.delivery_sum,
            Cart.status,
            Cart.is_paid,
            Cart.is_active,
            Cart.is_canceled,
            Cart.is_shipped,
            Cart.promo_code,
        )
        .where(Cart.user_id == user_id)
        .order_by(Cart.created_at.desc())
        .limit(recent_n)
    )).all()

    lines_total = int(it.lines_total or 0)
    qty_total = int(it.qty_total or 0)
    products_distinct = int(it.products_distinct or 0)
    positions_distinct = int(it.positions_distinct or 0)

    parts: list[str] = [f"📊 <b>Аналитика заказов пользователя</b>\n<i>User ID:</i> <b>{user_id}</b>", "\n".join(
        [
            "",
            "🧾 <u>Сводка</u>",
            f"🛍️ Заказов: <b>{carts_total}</b> (за {days} дней: <b>{int(t.carts_last_days_cnt or 0)}</b>)",
            f"💰 Сумма: <b>{sum_total:.2f}₽</b> | 🚚 Доставка: <b>{delivery_total:.2f}₽</b>",
            f"🎁 Реф.выплаты: <b>{promo_total:.2f}₽</b>",
            f"✅ Оплачено: <b>{int(t.paid_cnt or 0)}</b> | ❌ Не оплачено: <b>{int(t.unpaid_cnt or 0)}</b>",
            f"🟢 Активные: <b>{int(t.active_cnt or 0)}</b> | ⚫ Неактивные: <b>{int(t.inactive_cnt or 0)}</b>",
            f"📦 Отправлено: <b>{int(t.shipped_cnt or 0)}</b> | ⛔ Отменено: <b>{int(t.canceled_cnt or 0)}</b>",
            f"🏷️ С промокодом: <b>{int(t.with_promo_cnt or 0)}</b>",
            f"📈 Средний чек: <b>{avg_sum:.2f}₽</b>",
            f"🕒 Первый: <i>{_fmt_dt(t.first_cart_at)}</i>",
            f"🕓 Последний: <i>{_fmt_dt(t.last_cart_at)}</i>",
        ]
    ), "\n".join(
        [
            "",
            "📦 <u>Позиции</u>",
            f"• строк: <b>{lines_total}</b> | всего штук: <b>{qty_total}</b>",
            f"• уникальных продуктов: <b>{products_distinct}</b>",
            f"• уникальных позиций: <b>{positions_distinct}</b>",
            f"• уникальных категорий: <b>{int(cats_distinct)}</b>",
        ]
    )]

    if status_rows:
        parts.append("\n📌 <u>Статусы</u>")
        for s, cnt in status_rows[:10]:
            parts.append(f"• {s or 'NULL'}: <b>{int(cnt)}</b>")

    if cat_rows:
        parts.append("\n🗂️ <u>Топ категорий</u>")
        for cat_id, cat_name, qty, rev, prod_cnt in cat_rows:
            parts.append(
                f"• {cat_name}: <b>{int(qty)}</b> шт, <b>{_money(rev):.2f}₽</b>, товаров <b>{int(prod_cnt)}</b>"
            )

    if top_positions_rows:
        parts.append("\n⭐ <u>Топ позиций</u>")
        for product_id, product_name, feature_id, feature_name, qty, rev in top_positions_rows:
            pname = product_name or "Без названия"
            grams = feature_name
            parts.append(
                f"• <b>{pname}</b> — <i>{grams}</i> — "
                f"<b>{int(qty)}</b> шт (≈ <b>{_money(rev):.2f}₽</b>)"
            )

    if recent_rows:
        parts.append("\n🕓 <u>Последние заказы</u>")
        for (cid, created_at, ssum, dsum, status, is_paid, is_active, is_canceled, is_shipped, promo_code) in recent_rows:
            flags = []
            if is_paid: flags.append("✅ paid")
            if is_shipped: flags.append("📦 shipped")
            if is_canceled: flags.append("⛔ canceled")
            if is_active: flags.append("🟢 active")
            flags_s = ", ".join(flags) if flags else "—"

            line = (
                f"• <b>Заказ #{cid}</b> — <i>{_fmt_dt(created_at)}</i>\n"
                f"  Статус: <b>{status or '—'}</b>\n"
                f"  Сумма: <b>{_money(ssum):.2f}₽</b>, доставка <b>{_money(dsum):.2f}₽</b>\n"
                f"  Флаги: <i>{flags_s}</i>\n"
            )
            if promo_code: line += f"\n  Промокод: <b>{promo_code}</b>"
            parts.append(line)

    return "\n".join(parts)


async def cart_analysis_text(db: AsyncSession, cart_id: int) -> str:
    """
    Receives cart_id and returns a human/Telegram-friendly analysis text about this cart.
    Loads: cart.items -> (product + feature), cart.user, cart.promo, product.tg_categories.
    """

    stmt = (
        select(Cart)
        .where(Cart.id == cart_id)
        .options(
            selectinload(Cart.items)
            .selectinload(CartItem.product)
            .selectinload(Product.tg_categories),
            selectinload(Cart.items).selectinload(CartItem.feature),
            selectinload(Cart.user),
            joinedload(Cart.promo),
            )
    )

    cart: Optional[Cart] = (await db.execute(stmt)).scalars().first()
    if not cart:
        return f"❌ Корзина/заказ не найден: <code>{cart_id}</code>"

    lines = []
    qty_total = 0
    items_total = Decimal("0")

    for it in (cart.items or []):
        qty = int(getattr(it, "quantity", 1) or 1)
        qty_total += qty

        product = getattr(it, "product", None)
        feature = getattr(it, "feature", None)

        p_name = _s(product, "name", "Без названия")
        p_code = _s(product, "code", "")
        f_name = _s(feature, "name", "")  # обычно дозировка/вариация
        unit_price = _money(getattr(feature, "price", None))
        line_total = unit_price * qty
        items_total += line_total

        # категории (tg)
        cats = []
        if product and getattr(product, "tg_categories", None):
            cats = [getattr(c, "name", "") for c in product.tg_categories if getattr(c, "name", None)]
        cats_text = f" • 🏷 {', '.join(cats)}" if cats else ""

        title = f"• <b>{p_name}</b>"
        if p_code:
            title += f" <i>({p_code})</i>"
        if f_name:
            title += f"\n  ↳ {f_name}"
        title += (
            f"\n  кол-во: <b>{qty}</b>"
            f" • цена: <b>{unit_price}</b>₽"
            f" • сумма: <b>{line_total}</b>₽{cats_text}"
        )

        lines.append(title)

    cart_sum = _money(getattr(cart, "sum", None))
    delivery_sum = _money(getattr(cart, "delivery_sum", None))
    promo_gains = _money(getattr(cart, "promo_gains", None))
    grand_total_calc = items_total + delivery_sum
    grand_total_saved = cart_sum + delivery_sum

    # ---- блок пользователя ----
    user = getattr(cart, "user", None)
    user_bits = []
    if user:
        user_bits.append(f"👤 user_id: <code>{_s(user, 'tg_id', _s(user, 'id', str(cart.user_id)))}</code>")
        full_name = _s(user, "full_name", "").strip()
        if not full_name:
            full_name = f"{_s(user,'name','').strip()} {_s(user,'surname','').strip()}".strip()
        if full_name:
            user_bits.append(f"   имя: <b>{full_name}</b>")
        uname = _s(user, "username", "").strip()
        if uname:
            user_bits.append(f"   username: @{uname.lstrip('@')}")
        phone = _s(user, "phone", "").strip()
        tg_phone = _s(user, "tg_phone", "").strip()
        if phone or tg_phone:
            ph = " / ".join([p for p in [phone, tg_phone] if p])
            user_bits.append(f"   телефон: <code>{ph}</code>")
    else:
        user_bits.append(f"👤 user_id: <code>{cart.user_id}</code>")

    # ---- статус / мета ----
    status_flags = []
    status_flags.append("✅ оплачено" if getattr(cart, "is_paid", False) else "⏳ не оплачено")
    status_flags.append("🟢 активна" if getattr(cart, "is_active", False) else "⚪ неактивна")
    if getattr(cart, "is_canceled", False):
        status_flags.append("❌ отменено")
    if getattr(cart, "is_shipped", False):
        status_flags.append("📦 отправлено")

    promo_code = _s(cart, "promo_code", "").strip()
    promo_txt = ""
    if promo_code:
        promo_owner = _s(getattr(cart, "promo", None), "owner_name", "").strip()
        promo_txt = f"\n🎟 промокод: <code>{promo_code}</code>" + (f" • владелец: <b>{promo_owner}</b>" if promo_owner else "")
        promo_txt += f"\n💸 выгода по промо: <b>{promo_gains}</b>₽ • начислено: <b>{'да' if getattr(cart,'promo_gains_given',False) else 'нет'}</b>"

    delivery_string = _s(cart, "delivery_string", "").strip()
    commentary = _s(cart, "commentary", "").strip()
    yandex_request_id = _s(cart, "yandex_request_id", "").strip()
    status_str = _s(cart, "status", "").strip()

    created_at = _s(cart, "created_at", "")
    updated_at = _s(cart, "updated_at", "")

    diff_note = ""
    if items_total != cart_sum:
        diff_note = f"\n⚠️ <i>Несовпадение сумм:</i> по позициям=<b>{items_total}</b>₽ vs cart.sum=<b>{cart_sum}</b>₽"

    header = f"🧾 <b>{_s(cart,'name',f'Заказ #{cart.id}')}</b>\n🆔 cart_id: <code>{cart.id}</code>"
    meta = (
            f"\n\n📌 статус: <b>{', '.join(status_flags)}</b>"
            + (f"\n📄 статус (текст): <i>{status_str}</i>" if status_str else "")
            + (f"\n🪪 yandex_request_id: <code>{yandex_request_id}</code>" if yandex_request_id else "")
            + (f"\n🚚 доставка: <i>{delivery_string}</i>" if delivery_string else "")
            + (f"\n💬 комментарий: <i>{commentary}</i>" if commentary else "")
            + f"\n⏱ создано: <code>{created_at}</code>\n🔁 обновлено: <code>{updated_at}</code>"
    )

    totals = (
        f"\n\n📦 позиций: <b>{len(cart.items or [])}</b> • всего кол-во: <b>{qty_total}</b>"
        f"\n🧮 сумма по позициям (пересчёт): <b>{items_total}</b>₽"
        f"\n🧾 cart.sum (в базе): <b>{cart_sum}</b>₽"
        f"\n🚚 доставка (в базе): <b>{delivery_sum}</b>₽"
        f"\n💰 итог (пересчёт): <b>{grand_total_calc}</b>₽"
        f"\n💰 итог (как в базе): <b>{grand_total_saved}</b>₽"
        f"{diff_note}"
    )

    items_block = "\n\n🧷 <b>Состав заказа</b>\n" + ("\n".join(lines) if lines else "— пусто —")
    user_block = "\n\n" + "\n".join(user_bits) if user_bits else ""

    return header + user_block + meta + promo_txt + totals + items_block