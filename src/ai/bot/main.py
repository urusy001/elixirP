import asyncio
import copy
import logging
import re

from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
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
    BOT_NAMES, NEW_OPENAI_API, PROFESSOR_OPENAI_API, PROFESSOR_ASSISTANT_ID, MOSCOW_TZ,
)
from src.ai.bot.handlers import *
from src.ai.bot.keyboards import user_keyboards
from src.ai.bot.middleware import ContextMiddleware
from src.ai.bot.texts import user_texts
from src.ai.client import ProfessorClient
from src.helpers import split_text, MAX_TG_MSG_LEN
from src.webapp import get_session
from src.webapp.crud import get_users, create_user, update_user, update_premium_requests, upsert_user
from src.webapp.schemas import UserUpdate, UserCreate


class ProfessorBot(Bot):
    def __init__(self, api_key: str, bot_name: str):
        super().__init__(api_key, default=DefaultBotProperties(parse_mode="html"))

        self.__logger = logging.getLogger(f"{self.__class__.__name__}::{bot_name}")
        self.__logger.setLevel(logging.INFO)

        log_file = LOGS_DIR / f"{bot_name}.txt"
        log_file.parent.mkdir(parents=True, exist_ok=True)

        if not any(
                isinstance(h, logging.FileHandler)
                and getattr(h, "baseFilename", None) == str(log_file)
                for h in self.__logger.handlers
        ):
            fh = logging.FileHandler(log_file, encoding="utf-8")
            fh.setFormatter(
                logging.Formatter(
                    "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                    "%Y-%m-%d %H:%M:%S",
                )
            )
            self.__logger.addHandler(fh)

    @property
    def log(self):
        return self.__logger

    # ---------------- CREATE USER ----------------
    async def create_user(self, user_id: int, phone: str, name: str = None, surname: str = None) -> UserCreate:
        thread_id = await professor_client.create_thread()
        user_create = UserCreate(tg_id=user_id, tg_phone=phone, thread_id=thread_id)

        async with get_session() as session:
            user = await upsert_user(session, user_create)

        self.__logger.info("Created new user: %s, phone=%s", user_id, phone)
        return thread_id

    # ---------------- PARSE RESPONSE ----------------
    async def parse_response(self, response: dict, message: Message, back_menu: bool = False, adv: bool = False):
        user_id = message.from_user.id
        logger = self.__logger  # one logger per bot

        logger.info(
            "INCOMING message | user_id=%s | text=%r",
            user_id,
            getattr(message, "text", None),
        )

        files: list[str] = response.get("files") or []
        text: str = (response.get("text") or "").strip()
        input_tokens: int = int(response.get("input_tokens") or 0)
        output_tokens: int = int(response.get("output_tokens") or 0)

        logger.info(
            "MODEL RESPONSE (raw) | user_id=%s | files=%d | text_len=%d | "
            "input_tokens=%d | output_tokens=%d",
            user_id,
            len(files),
            len(text),
            input_tokens,
            output_tokens,
        )

        match = re.search(r"BLOCK_USER_TG_(\d+)", text, re.IGNORECASE)
        if match:
            days = int(match.group(1))
            text = re.sub(r"BLOCK_USER_TG_\d+", "", text, flags=re.IGNORECASE).strip()
            blocked_until = (
                datetime.now() + timedelta(days=days) if days > 0 else datetime.max
            )

            logger.warning(
                "Blocking user for %s days (until %s)", days, blocked_until
            )

            async with get_session() as session:
                await update_user(
                    session, user_id, UserUpdate(blocked_until=blocked_until)
                )

        if input_tokens or output_tokens:
            async with get_session() as session:
                db_users = await get_users(session)
                db_user = next((u for u in db_users if u.tg_id == user_id), None)

                prev_input = getattr(db_user, "input_tokens", 0) if db_user else 0
                prev_output = getattr(db_user, "output_tokens", 0) if db_user else 0

                new_input = prev_input + input_tokens
                new_output = prev_output + output_tokens

                logger.info(
                    "Token usage | +in=%d +out=%d | prev=%d/%d | new=%d/%d",
                    input_tokens,
                    output_tokens,
                    prev_input,
                    prev_output,
                    new_input,
                    new_output,
                )

                await update_user(
                    session,
                    user_id,
                    UserUpdate(
                        input_tokens=new_input,
                        output_tokens=new_output,
                    ),
                )

            self.__logger.info(
                "Updated tokens for %s: +%d/%d (total %d/%d)",
                user_id,
                input_tokens,
                output_tokens,
                new_input,
                new_output,
            )
        keyboard = copy.deepcopy(user_keyboards.backk)
        if adv:
            keyboard.inline_keyboard.append([
                InlineKeyboardButton(text="Ознакомиться с программой", url="https://t.me/obucheniepeptid/32"),
                InlineKeyboardButton(text="Попасть на обучение", url="https://www.peptidecourse.ru/"),
            ])
        if not files and not text:
            logger.warning("EMPTY response (no files, no text)")
            return await message.reply("oshibochka vishla da", reply_markup=keyboard if back_menu == True else ReplyKeyboardRemove())

        if files:
            logger.info("OUTGOING response has %d file(s)", len(files))
            if len(files) == 1:
                caption = re.sub(r"【[^】]*】", "", text[:900])+(user_texts.blockquote if adv else '') or None
                logger.info(
                    "OUTGOING single photo | caption_len=%d",
                    len(caption or ""),
                )
                return await message.reply_photo(
                    FSInputFile(files[0]),
                    caption=caption,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=keyboard if back_menu == True else ReplyKeyboardRemove(),
                )
            else:
                media = [
                    InputMediaPhoto(media=FSInputFile(f), parse_mode=ParseMode.MARKDOWN)
                    for f in files
                ]
                if text: media[0].caption = re.sub(r"【[^】]*】", "", text[:1024])
                logger.info(
                    "OUTGOING media group | first_caption_len=%d",
                    len(media[0].caption or ""),
                )
                return await message.reply_media_group(media)

        if len(text) > MAX_TG_MSG_LEN:
            logger.info("OUTGOING long text | len=%d | splitting", len(text))
            chunks = await split_text(text)
            for idx, chunk in enumerate(chunks[:-1], start=1):
                clean_chunk = re.sub(r"【[^】]*】", "", chunk)
                logger.info(
                    "OUTGOING chunk %d/%d | len=%d",
                    idx,
                    len(chunks),
                    len(clean_chunk),
                )
                await message.reply(
                    clean_chunk,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=ReplyKeyboardRemove(),
                )
            return await message.reply(re.sub(r"【[^】]*】", "", chunks[-1])+(user_texts.blockquote if adv else ''), parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard if back_menu == True else ReplyKeyboardRemove())

        clean_text = re.sub(r"【[^】]*】", "", text)
        logger.info(
            "OUTGOING text | len=%d | preview=%r",
            len(clean_text),
            clean_text[:200],
        )
        return await message.reply(
            clean_text+(user_texts.blockquote if adv else ''),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard if back_menu == True else ReplyKeyboardRemove()
        )


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
    await new_bot.delete_webhook(drop_pending_updates=False)
    await new_dp.start_polling(new_bot)
