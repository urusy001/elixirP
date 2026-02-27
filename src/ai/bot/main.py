from __future__ import annotations

import copy
import logging
import re

from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, FSInputFile, InputMediaPhoto, ReplyKeyboardRemove, InlineKeyboardButton

from config import (
    PROFESSOR_BOT_TOKEN,
    DOSE_BOT_TOKEN,
    DOSE_ASSISTANT_ID,
    DOSE_OPENAI_API,
    NEW_BOT_TOKEN,
    NEW_ASSISTANT_ID,
    LOGS_DIR,
    BOT_NAMES, NEW_OPENAI_API, PROFESSOR_OPENAI_API, PROFESSOR_ASSISTANT_ID, UFA_TZ,
)
from src.ai.bot.handlers import *
from src.ai.helpers import split_text, MAX_TG_MSG_LEN
from src.ai.bot.keyboards import user_keyboards
from src.ai.bot.middleware import ContextMiddleware
from src.ai.bot.texts import user_texts
from src.ai.client import ProfessorClient
from src.ai.webapp_client import webapp_client


class ProfessorBot(Bot):
    def __init__(self, api_key: str, bot_name: str):
        super().__init__(api_key, default=DefaultBotProperties(parse_mode="html"))

        self.__logger = logging.getLogger(f"{self.__class__.__name__}::{bot_name}")
        self.__logger.setLevel(logging.INFO)

        log_file = LOGS_DIR / f"{bot_name}.txt"
        log_file.parent.mkdir(parents=True, exist_ok=True)

        if not any(isinstance(h, logging.FileHandler) and getattr(h, "baseFilename", None) == str(log_file) for h in self.__logger.handlers):
            fh = logging.FileHandler(log_file, encoding="utf-8")
            fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S"))
            self.__logger.addHandler(fh)

    @property
    def log(self): return self.__logger

    async def create_user(self, user_id: int, phone: str, name: str = None, surname: str = None) -> str:
        thread_id = await professor_client.create_thread()
        await webapp_client.upsert_user({"tg_id": user_id, "tg_phone": phone, "name": name, "surname": surname, "thread_id": thread_id})
        self.__logger.info("Created new user: %s, phone=%s", user_id, phone)
        return thread_id

    async def _reply_text_safe(self, message: Message, text: str, *, reply_markup=None) -> Message:
        try: return await message.reply(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
        except TelegramBadRequest as e:
            self.__logger.warning("Markdown failed for text reply, retrying plain. err=%s", e)
            return await message.reply(text, reply_markup=reply_markup)

    async def _reply_photo_safe(self, message: Message, photo: FSInputFile, *, caption: str | None, reply_markup=None):
        try: return await message.reply_photo(photo, caption=caption, parse_mode=ParseMode.MARKDOWN if caption else None, reply_markup=reply_markup)
        except TelegramBadRequest as e:
            self.__logger.warning("Markdown failed for photo caption, retrying plain. err=%s", e)
            return await message.reply_photo(photo, caption=caption, reply_markup=reply_markup)

    async def _reply_media_group_safe(self, message: Message, files: list[str], *, caption: str | None = None):
        media_md = [InputMediaPhoto(media=FSInputFile(f), parse_mode=ParseMode.MARKDOWN) for f in files]
        if caption: media_md[0].caption = caption
        try: return await message.reply_media_group(media_md)
        except TelegramBadRequest as e: self.__logger.warning("Markdown failed for media group, retrying plain. err=%s", e)
        media_plain = [InputMediaPhoto(media=FSInputFile(f)) for f in files]
        if caption: media_plain[0].caption = caption
        return await message.reply_media_group(media_plain)

    async def parse_response(self, response: dict, message: Message, back_menu: bool = False, adv: bool = False):
        user_id = message.from_user.id
        self.__logger = self.__logger
        self.__logger.info("INCOMING message | user_id=%s | text=%r",user_id, getattr(message, "text", None))
        files: list[str] = response.get("files") or []
        text: str = (response.get("text") or "").strip()
        input_tokens: int = int(response.get("input_tokens") or 0)
        output_tokens: int = int(response.get("output_tokens") or 0)
        self.__logger.info("MODEL RESPONSE (raw) | user_id=%s | files=%d | text_len=%d | input_tokens=%d | output_tokens=%d",user_id, len(files), len(text), input_tokens, output_tokens)
        match = re.search(r"BLOCK_USER_TG_(\d+)", text, re.IGNORECASE)
        if match:
            days = int(match.group(1))
            text = re.sub(r"BLOCK_USER_TG_\d+", "", text, flags=re.IGNORECASE).strip()
            blocked_until = (datetime.now() + timedelta(days=days) if days > 0 else datetime.max)
            self.__logger.warning("Blocking user for %s days (until %s)", days, blocked_until)
            await webapp_client.update_user(user_id, {"blocked_until": blocked_until})

        if input_tokens or output_tokens:
            db_user = await webapp_client.get_user("tg_id", user_id)
            prev_input = getattr(db_user, "input_tokens", 0) if db_user else 0
            prev_output = getattr(db_user, "output_tokens", 0) if db_user else 0
            new_input = prev_input + input_tokens
            new_output = prev_output + output_tokens
            await webapp_client.update_user(user_id, {"input_tokens": new_input, "output_tokens": new_output})
            self.__logger.info("Token usage | +in=%d +out=%d | prev=%d/%d | new=%d/%d", input_tokens, output_tokens, prev_input, prev_output, new_input, new_output)
            self.__logger.info("Updated tokens for %s: +%d/%d (total %d/%d)", user_id, input_tokens, output_tokens, new_input, new_output)

        keyboard = copy.deepcopy(user_keyboards.backk)
        if adv: keyboard.inline_keyboard.append([InlineKeyboardButton(text="Ознакомиться с программой", url="https://t.me/obucheniepeptid/32"), InlineKeyboardButton(text="Попасть на обучение", url="https://www.peptidecourse.ru/")])
        reply_markup = keyboard if back_menu else ReplyKeyboardRemove()
        if not files and not text:
            self.__logger.warning("EMPTY response (no files, no text)")
            return await self._reply_text_safe(message, "oshibochka vishla da", reply_markup=reply_markup)

        clean_text = re.sub(r"【[^】]*】", "", text).strip()
        if not files and not clean_text:
            self.__logger.warning("EMPTY response after citation cleanup")
            return await self._reply_text_safe(message, "oshibochka vishla da", reply_markup=reply_markup)
        if files:
            self.__logger.info("OUTGOING response has %d file(s)", len(files))
            if len(files) == 1:
                caption = (clean_text[:900] + (user_texts.blockquote if adv else "")) or None
                self.__logger.info("OUTGOING single photo | caption_len=%d", len(caption or ""))
                return await self._reply_photo_safe(message, FSInputFile(files[0]), caption=caption, reply_markup=reply_markup)

            else:
                caption0 = clean_text[:1024] if clean_text else None
                self.__logger.info("OUTGOING media group | first_caption_len=%d", len(caption0 or ""))
                return await self._reply_media_group_safe(message, files, caption=caption0)

        out_text = clean_text + (user_texts.blockquote if adv else "")
        if len(out_text) > MAX_TG_MSG_LEN:
            self.__logger.info("OUTGOING long text | len=%d | splitting", len(out_text))
            chunks = await split_text(out_text)

            for idx, chunk in enumerate(chunks[:-1], start=1):
                self.__logger.info("OUTGOING chunk %d/%d | len=%d", idx, len(chunks), len(chunk))
                await self._reply_text_safe(message, chunk, reply_markup=ReplyKeyboardRemove())

            return await self._reply_text_safe(message, chunks[-1], reply_markup=reply_markup)

        self.__logger.info("OUTGOING text | len=%d | preview=%r", len(out_text), out_text)
        return await self._reply_text_safe(message, out_text, reply_markup=reply_markup)

professor_bot = ProfessorBot(PROFESSOR_BOT_TOKEN, BOT_NAMES[PROFESSOR_BOT_TOKEN])
professor_client = ProfessorClient(PROFESSOR_OPENAI_API, PROFESSOR_ASSISTANT_ID)
professor_dp = Dispatcher(storage=MemoryStorage())
professor_dp.include_routers(professor_admin_router, professor_user_router)
professor_dp.message.middleware(ContextMiddleware(professor_bot, professor_client))
professor_dp.callback_query.middleware(ContextMiddleware(professor_bot, professor_client))

dose_bot = ProfessorBot(DOSE_BOT_TOKEN, BOT_NAMES[DOSE_BOT_TOKEN])
dose_client = ProfessorClient(DOSE_OPENAI_API, DOSE_ASSISTANT_ID)
dose_dp = Dispatcher(storage=MemoryStorage())
dose_dp.include_routers(dose_admin_router, dose_user_router)
dose_dp.message.middleware(ContextMiddleware(dose_bot, dose_client))
dose_dp.callback_query.middleware(ContextMiddleware(dose_bot, dose_client))

new_bot = ProfessorBot(NEW_BOT_TOKEN, BOT_NAMES[NEW_BOT_TOKEN])
new_client = ProfessorClient(NEW_OPENAI_API, NEW_ASSISTANT_ID)
new_dp = Dispatcher(storage=MemoryStorage())
new_dp.include_routers(new_chat_router, new_admin_router, new_user_router)
new_dp.message.middleware(ContextMiddleware(new_bot, new_client))
new_dp.callback_query.middleware(ContextMiddleware(new_bot, new_client))


async def run_professor_bot():
    await professor_bot.delete_webhook(drop_pending_updates=False)
    await professor_dp.start_polling(professor_bot)


async def run_dose_bot():
    await dose_bot.delete_webhook(drop_pending_updates=False)
    await dose_dp.start_polling(dose_bot)


async def run_new_bot():
    await new_bot.delete_webhook(drop_pending_updates=True)
    await new_dp.start_polling(new_bot)
