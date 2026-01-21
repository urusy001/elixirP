import logging
import phonenumbers
import re

from telethon import TelegramClient
from typing import Iterable, Optional
from telethon.tl.functions.contacts import ImportContactsRequest
from telethon.tl.types import InputPhoneContact

from config import TELETHON_API_ID, TELETHON_API_HASH

logger = logging.getLogger("telethon")
client = TelegramClient(TELETHON_API_ID, TELETHON_API_ID, TELETHON_API_HASH)


def normalize_phone(raw: str, default_regions: Iterable[str] = ("US", "AM", "RU", "UA", "BY", "AZ", "KZ", "KG", "MD", "TJ", "TM", "UZ", "GE")) -> Optional[str]:
    def _clean(raw: str) -> str:
        raw = raw.strip()
        if raw.startswith("+"): return "+" + re.sub(r"\D", "", raw[1:])
        return re.sub(r"\D", "", raw)

    s = _clean(raw)
    if not s: return None

    if s.startswith("+"):
        try:
            n = phonenumbers.parse(s, None)
            return phonenumbers.format_number(n, phonenumbers.PhoneNumberFormat.E164) if phonenumbers.is_valid_number(n) else None
        except phonenumbers.NumberParseException: return None

    for region in default_regions:
        try:
            n = phonenumbers.parse(s, region)
            if phonenumbers.is_valid_number(n): return phonenumbers.format_number(n, phonenumbers.PhoneNumberFormat.E164)
        except phonenumbers.NumberParseException: continue

    return raw

async def get_user_id_by_phone(phone: str):
    normalized = normalize_phone(phone)

    result = await client(ImportContactsRequest([
        InputPhoneContact(
            client_id=0,
            phone=normalized,
            first_name="x",
            last_name=""
        )
    ]))
    print(result)

    if result.users: return result.users[0].id
    return None
