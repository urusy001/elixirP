from aiogram import Router
from aiogram.types import Message

from config import LOGS_DIR
from src.antispam.test_classifier import is_spam
from src.helpers import append_message_to_csv

router = Router(name="chat")
file_path = LOGS_DIR / "messages.csv"

@router.message(lambda message: "peptide_rus" == getattr(message.chat, "username", ""))
async def handle_chat_message(message: Message):
    if not message.text.strip(): pass
    else:
        result, p = await is_spam(message.text)
        await append_message_to_csv(message.text, int(result))
