import asyncio
import hashlib
import hmac
import random
import re
import string

from typing import Optional
from aiogram.types import Message
from transliterate import translit
from functools import wraps
from aiogram import Bot

from config import YOOKASSA_SECRET_KEY

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
