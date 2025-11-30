from __future__ import annotations

import asyncio
import csv
import hashlib
import hmac
import json
import random
import re
import string
import time

from functools import wraps
from logging import Logger
from typing import Optional, Literal
from urllib.parse import parse_qsl
from aiogram import Bot
from aiogram.types import Message
from fastapi import HTTPException
from pydantic import BaseModel
from transliterate import translit

from config import YOOKASSA_SECRET_KEY, CSV_PATH, ELIXIR_CHAT_ID, AI_BOT_TOKEN3

MAX_TG_MSG_LEN = 4096  # Telegram limit


def with_typing(func):
    """
    Decorator that sends 'typing...' action while the wrapped handler is running.
    Automatically detects Bot from handler args.
    """

    @wraps(func)
    async def wrapper(*args, **kwargs):
        bot: Bot | None = None
        chat_id: int | None = None

        # Try to detect bot and chat_id automatically
        for arg in args:
            if isinstance(arg, Bot):
                bot = arg
            elif isinstance(arg, Message):
                chat_id = arg.chat.id

        if not bot:
            bot = kwargs.get("ai/bot") or kwargs.get("professor_bot")
        if not chat_id:
            if "message" in kwargs:
                chat_id = kwargs["message"].chat.id

        if not bot or not chat_id:
            raise ValueError("Could not detect Bot or chat_id for typing decorator")

        async def loop():
            try:
                while True:
                    try:
                        await bot.send_chat_action(chat_id, "typing")
                    except Exception:
                        pass
                    await asyncio.sleep(random.uniform(3, 5))
            except asyncio.CancelledError:
                return  # exit immediately when cancelled

        task = asyncio.create_task(loop())
        try:
            return await func(*args, **kwargs)
        finally:
            task.cancel()  # cancel immediately
            try:
                await task
            except asyncio.CancelledError:
                pass

    return wrapper


async def split_text(text: str, limit: int = MAX_TG_MSG_LEN) -> list[str]:
    """
    Splits long text into chunks safe for Telegram.
    Tries to split at paragraph or sentence boundaries.
    """
    chunks = []
    while len(text) > limit:
        split_idx = text.rfind("\n", 0, limit)
        if split_idx == -1:
            split_idx = text.rfind(". ", 0, limit)
        if split_idx == -1:
            split_idx = limit

        chunks.append(text[:split_idx].strip())
        text = text[split_idx:].strip()
    if text:
        chunks.append(text)
    return chunks


async def verify_signature(raw_body: bytes, signature_header: Optional[str]) -> bool:
    if not YOOKASSA_SECRET_KEY:
        return True
    if not signature_header:
        return False
    expected = hmac.new(YOOKASSA_SECRET_KEY.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header)


async def normalize(text: str) -> str:
    try:
        return translit(text, "ru", reversed=True).lower()
    except Exception:
        return text.lower()


def cypher_user_id(user_id: int) -> str:
    """
    Insert random 4–6 capital letters randomly inside user_id.
    Example: 12345 -> '12ABCD345' or 'A1234XYZ5'
    """
    letters = ''.join(random.choices(string.ascii_uppercase, k=random.randint(4, 6)))
    user_id_str = str(user_id)
    insert_pos = random.randint(0, len(user_id_str))
    return user_id_str[:insert_pos] + letters + user_id_str[insert_pos:]


def decypher_user_id(cyphered: str) -> int:
    """
    Remove all capital letters and return numeric user_id.
    Example: '12ABCD345' -> 12345
    """
    numeric = re.sub(r'[A-Z]', '', cyphered)
    return int(numeric)


EMAIL_REGEX = re.compile(
    r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
)


def extract_email(text: str) -> Optional[str]:
    """
    Extracts the first email address from the given string.
    Returns None if no email is found.
    """
    if not text:
        return None

    match = EMAIL_REGEX.search(text)
    return match.group(0) if match else None

# src/webapp/utils/normalize.py
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, Integer, String, DateTime, Numeric, Boolean
from sqlalchemy.orm.attributes import InstrumentedAttribute

from src.webapp.models.user import User  # adjust import to where your model lives


_NULLY = {None, "", "null", "None", "NULL"}


def _get_user_column(name: str) -> InstrumentedAttribute:
    col = getattr(User, name, None)
    if col is None or not hasattr(col, "type"):
        raise ValueError(f"Unknown column name for User: {name!r}")
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

    # UNIX epoch (seconds)
    if s.isdigit():
        return datetime.fromtimestamp(int(s), tz=timezone.utc)

    # ISO with trailing 'Z'
    if s.endswith("Z"):
        # Python <3.11: fromisoformat doesn't accept 'Z'
        try:
            return datetime.fromisoformat(s[:-1]).replace(tzinfo=timezone.utc)
        except Exception:
            pass

    # Plain ISO-8601 (may be naive or aware)
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

    # Normalize "null-like" inputs for nullable columns
    is_nullable = getattr(col.expression, "nullable", True)  # fallback True
    if raw_value in _NULLY and is_nullable:
        return None

    # Cast by SQLAlchemy type family
    if isinstance(col_type, (Integer, BigInteger)):
        return int(raw_value)

    if isinstance(col_type, String):
        return str(raw_value) if raw_value is not None else None

    if isinstance(col_type, DateTime):
        return _coerce_datetime(raw_value)

    if isinstance(col_type, Numeric):
        return Decimal(str(raw_value))

    if isinstance(col_type, Boolean):
        s = str(raw_value).strip().lower()
        return s in {"1", "true", "t", "yes", "y", "on"}

    # Fallback: return as-is (string)
    return raw_value

from datetime import datetime
from typing import Any, Dict


def format_order_for_amocrm(
        order_number: int | str,
        payload: Dict[str, Any],
        delivery_service: str,
        tariff: str | None,
) -> str:
    """
    Format Telegram checkout payload into AmoCRM-friendly Russian text.

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

    # ---- Date ----
    order_date = datetime.now().strftime("%d.%m.%Y")

    # ---- Items ----
    lines_items: list[str] = []
    for idx, item in enumerate(items, start=1):
        name = item.get("name", "Товар")
        qty = item.get("qty", 1)
        subtotal = int(item.get("subtotal", 0))
        subtotal_str = f"{subtotal:,}".replace(",", " ")  # 37260 -> "37 260"
        lines_items.append(f"{idx}. {name} {qty}шт. — {subtotal_str}руб.")

    items_block = "\n".join(lines_items) if lines_items else "Товары не указаны."

    # ---- Delivery text (CDEK vs Yandex) ----
    delivery_service_norm = (delivery_service or "").strip().upper()
    tariff_norm = (tariff or "").strip().lower() if tariff is not None else ""

    postal_code = address_data.get("postal_code") or ""
    formatted_cdek_addr = address_data.get("formatted") or address_data.get("name")
    # Yandex uses "address"
    yandex_addr = address_data.get("address") or ""
    yandex_name = address_data.get("name") or ""  # for self_pickup PVZ label

    delivery_mode = (delivery.get("deliveryMode") or "").strip()  # for Yandex

    if delivery_service_norm == "CDEK":
        # CDEK uses our explicit tariff param
        if tariff_norm == "office":
            prefix = "Доставка: Пункт выдачи СДЕК"
        elif tariff_norm == "door":
            prefix = "Доставка: Курьер СДЭК"
        else:
            prefix = "Доставка: СДЭК"

        delivery_line = f"{prefix}: {postal_code}, {formatted_cdek_addr}".strip()

    elif delivery_service_norm == "YANDEX":
        # Yandex uses deliveryMode + address.address
        if delivery_mode == "self_pickup":
            # данные из address: {code, address, name, phone, schedule}
            base = yandex_addr
            if yandex_name:
                base = f"{yandex_addr} ({yandex_name})"
            prefix = "Доставка: Пункт выдачи Яндекс"
            delivery_line = f"{prefix}: {base}".strip()

        elif delivery_mode in ("time_interval", "door"):
            prefix = "Доставка: Яндекс до двери"
            delivery_line = f"{prefix}: {yandex_addr}".strip()

        else:
            prefix = "Доставка: Яндекс ПВЗ"
            delivery_line = f"{prefix}: {yandex_addr}".strip()

    else:
        # generic fallback for any other service
        base_addr = formatted_cdek_addr or yandex_addr
        prefix = f"Доставка: {delivery_service}"
        delivery_line = f"{prefix}: {postal_code + ', ' if postal_code else ''}{base_addr}".strip()

    # ---- Contact info ----
    name = contact.get("name") or ""
    surname = contact.get("surname") or ""
    full_name = (surname + " " + name).strip() or "Не указано"

    phone = contact.get("phone") or "Не указан"
    email = contact.get("email") or "Не указан"

    # ---- Final text ----
    text = (
        f"Заказ №{order_number} с Магазина Телеграм\n"
        f"Дата заказа: {order_date}\n"
        f"Cостав заказа:\n"
        f"{items_block}\n\n"
        f"{delivery_line}\n\n"
        f"Имя клиента: {full_name}\n"
        f"Номер телефона: {phone}\n"
        f"Email: {email}\n\n"
        f"Промо-код: Не указано\n"
        f"Комментарий к заказу: Не указан"
    )

    return text

def normalize_address_for_cf(address: object, service: Literal["cdek", "yandex"] | None = "cdek", ) -> str | None:
        """
        Takes either:
        - string address
        - CDEK/Yandex address dict (like your example)
        Returns a short string <= 255 chars suitable for Amo text CF.
        """
        if not address:
            return None

        # Already a string
        if isinstance(address, str):
            s = address
        # Dict from CDEK/Yandex
        elif isinstance(address, dict):
            postal_code = address.get("postal_code")
            city = address.get("city")
            region = address.get("region")
            country_code = address.get("country_code")
            # typical CDEK/Yandex key for line
            line = address.get("address") or address.get("name")

            parts = [
                p for p in [
                    postal_code,
                    city,
                    region,
                    country_code,
                    line,
                ] if p
            ]
            s = ", ".join(map(str, parts))
        else:
            s = str(address)

        # Trim to Amo's 256 char limit (play safe with 255)
        if len(s) > 255:
            s = s[:255]
        return s or None

import html
import re
from bs4 import BeautifulSoup, Tag

# Базовый список допустимых тегов по Telegram
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

    # 1) Сначала раскрываем все HTML-сущности в нормальные символы,
    #    чтобы не осталось именованных типа &nbsp; &mdash; и т.п.,
    #    которые Телега не понимает
    raw_html = html.unescape(raw_html)

    soup = BeautifulSoup(raw_html, "html.parser")

    # 2) Заголовки в <b>
    for tag in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
        tag.name = "b"

    # 3) strong/em оставляем как есть (они разрешены), можно было бы и мапать в b/i
    #    но Телега их понимает напрямую

    # 4) Списки -> "• ..."
    for lst in soup.find_all(["ul", "ol"]):
        lines = []
        for li in lst.find_all("li", recursive=False):
            text = li.get_text(" ", strip=True)
            if text:
                lines.append(f"• {text}")
        lst.replace_with("\n".join(lines))

    # 5) <br> -> \n
    for br in soup.find_all("br"):
        br.replace_with("\n")

    # 6) <p> -> абзацы + пустая строка после
    for p in soup.find_all("p"):
        text = p.get_text(" ", strip=True)
        if text:
            p.replace_with(text + "\n")
        else:
            p.decompose()

    # 7) Обработка атрибутов и фильтрация тегов
    for tag in list(soup.find_all(True)):  # True = любой тег
        if not isinstance(tag, Tag):
            continue

        name = tag.name

        # всё, что не в ALLOWED_TAGS, разворачиваем
        if name not in ALLOWED_TAGS:
            tag.unwrap()
            continue

        # ----- специальные случаи по тегам -----

        if name == "span":
            # оставляем только spoiler: <span class="tg-spoiler">
            classes = tag.get("class", [])
            if "tg-spoiler" in classes:
                tag.attrs = {"class": "tg-spoiler"}
            else:
                tag.unwrap()

        elif name == "a":
            # только href
            href = tag.get("href")
            if href:
                tag.attrs = {"href": href}
            else:
                # без href смысла нет
                tag.unwrap()

        elif name == "tg-emoji":
            # только emoji-id
            emoji_id = tag.get("emoji-id")
            if emoji_id:
                tag.attrs = {"emoji-id": emoji_id}
            else:
                tag.unwrap()

        elif name == "code":
            # язык можно оставлять только если внутри <pre><code class="language-...">
            if isinstance(tag.parent, Tag) and tag.parent.name == "pre":
                cls = tag.get("class")
                if cls:
                    # class="language-python" и т.п. — оставляем
                    tag.attrs = {"class": cls}
                else:
                    tag.attrs = {}
            else:
                # одиночный <code> — без атрибутов
                tag.attrs = {}

        elif name == "pre":
            # pre без атрибутов
            tag.attrs = {}

        elif name == "blockquote":
            # разрешён только атрибут expandable
            if "expandable" in tag.attrs:
                tag.attrs = {"expandable": None}  # <blockquote expandable>
            else:
                tag.attrs = {}

        else:
            # все остальные разрешённые теги без атрибутов
            tag.attrs = {}

    # 8) Получаем HTML-строку обратно
    text = str(soup)

    # 9) Чистим лишние пустые строки
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = "\n".join(line.rstrip() for line in text.splitlines())

    return text.strip()

_csv_lock = asyncio.Lock()  # чтобы несколько хендлеров не писали одновременно

async def append_message_to_csv(text: str, label: int | str = 0) -> None:
    """
    Добавляет строку в messages.csv.
    csv.writer сам экранирует запятые, кавычки и переносы строк.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")  # чуть-чуть нормализуем

    async with _csv_lock:
        file_exists = CSV_PATH.exists()

        with CSV_PATH.open("a", encoding="utf-8", newline="") as f:
            writer = csv.writer(
                f,
                delimiter=",",
                quotechar='"',
                quoting=csv.QUOTE_MINIMAL,  # можно csv.QUOTE_ALL если хочешь всегда в кавычках
            )
            # если файл только что создан — пишем заголовок
            if not file_exists:
                writer.writerow(["Message", "Label"])

            writer.writerow([text, label])

async def _notify_user(message: Message, text: str, timer: float | None = None, logger: Logger = None) -> None:
    if logger: logger.info("Notify user %s | text_preview=%r | timer=%s", message.from_user.id, text[:100], timer)
    x = await message.answer(text, parse_mode="HTML")
    if timer:
        await asyncio.sleep(timer)
        await x.delete()
        if logger: logger.debug("Deleted notification message for user %s", message.from_user.id)


async def CHAT_ADMIN_FILTER(message: Message, bot: Bot) -> bool:
    # 1) Работаем только в нужном чате
    if getattr(message.chat, "id") not in [-1003182914098, ELIXIR_CHAT_ID]:
        return False

    # 2) Сообщение отправлено "от имени чата" (sender_chat)
    #    Такое вообще может сделать только админ, так что считаем это админом
    if message.sender_chat and message.sender_chat.id == message.chat.id:
        return True

    # 3) Обычный юзер (from_user) — проверяем через get_chat_member
    if message.from_user:
        member = await bot.get_chat_member(message.chat.id, message.from_user.id)
        return member.status in ("administrator", "creator")

    # 4) Всё остальное — не админ
    return False


class TelegramAuthPayload(BaseModel):
    initData: str
    initDataUnsafe: dict

def verify_telegram_init_data(init_data: str, bot_token: str = AI_BOT_TOKEN3, max_age_seconds: int = 300) -> dict:
    """
    Проверка initData от Telegram WebApp.
    Возвращает dict с полями (user, chat_instance, auth_date, ...) если все ок.
    Кидает HTTPException если подпись/время неверные.
    """
    if not bot_token: raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")

    data = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = data.pop("hash", None)

    if not received_hash: raise HTTPException(status_code=400, detail="Missing hash")
    check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))

    secret_key = hashlib.sha256(bot_token.encode("utf-8")).digest()
    computed_hash = hmac.new(secret_key, check_string.encode("utf-8"), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        print(1)
        raise HTTPException(status_code=401, detail="Invalid init data hash")

    auth_date_str = data.get("auth_date")
    if auth_date_str:
        try: auth_ts = int(auth_date_str)
        except ValueError: raise HTTPException(status_code=400, detail="Invalid auth_date")
        now = int(time.time())
        if now - auth_ts > max_age_seconds:
            print(2)
            raise HTTPException(status_code=401, detail="Init data is too old")

    user_raw = data.get("user")
    try: user = json.loads(user_raw) if user_raw else None
    except json.JSONDecodeError: raise HTTPException(status_code=400, detail="Invalid user JSON")

    data["user"] = user
    return data
