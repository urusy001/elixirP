import logging
import phonenumbers
from telethon import TelegramClient
from telethon.tl.functions.contacts import ImportContactsRequest
from telethon.tl.types import InputPhoneContact

from config import TELETHON_API_ID, TELETHON_API_HASH

logger = logging.getLogger("telethon")

client = TelegramClient(TELETHON_API_ID, TELETHON_API_ID, TELETHON_API_HASH)

def normalize_phone(phone: str, default_region: str = "RU") -> str:
    try:
        parsed = phonenumbers.parse(phone, default_region)
    except phonenumbers.NumberParseException as e:
        raise ValueError(f"Invalid phone number: {phone}") from e

    if not phonenumbers.is_valid_number(parsed):
        raise ValueError(f"Invalid phone number: {phone}")

    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164).removeprefix('+')


async def get_user_id_by_phone(phone: str, default_region: str = "RU"):
    normalized = normalize_phone(phone, default_region)

    result = await client(ImportContactsRequest([
        InputPhoneContact(
            client_id=0,
            phone=normalized,
            first_name="x",
            last_name=""
        )
    ]))

    if result.users: return result.users[0].id
    return None
