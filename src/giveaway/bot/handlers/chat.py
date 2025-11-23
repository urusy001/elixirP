import aiofiles
from aiogram import Router
from aiogram.types import Message

from config import LOGS_DIR

router = Router(name="chat")
file_path = LOGS_DIR / "messages.csv"

@router.message(lambda message: "peptide_rus" == getattr(message.chat, "username", ""))
async def handle_chat_message(message: Message):
    if not message.text.strip(): pass
    else:
        if not file_path.exists():
            with open(file_path, "w", encoding="utf-8") as f: f.write("message;label\n")

        async with aiofiles.open(file_path, mode="r", encoding="utf-8") as f:
            data = await f.readlines()

        data.append(f"{message.text.strip()};label\n")
        async with aiofiles.open(file_path, mode="w", encoding="utf-8") as f:
            await f.writelines(data)
