import logging
import re
from datetime import datetime, timedelta
from pathlib import Path  # 🔹 NEW

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, FSInputFile, InputMediaPhoto, ReplyKeyboardRemove

from config import AI_BOT_TOKEN, AI_BOT_TOKEN2, ASSISTANT_ID2, OPENAI_API_KEY2, AI_BOT_TOKEN3, ASSISTANT_ID3, LOGS_DIR, \
    BOT_NAMES
from src.ai.bot.handlers import *
from src.ai.bot.middleware import ContextMiddleware
from src.ai.client import ProfessorClient
from src.helpers import split_text, MAX_TG_MSG_LEN
from src.webapp import get_session
from src.webapp.crud import get_users, create_user, update_user
from src.webapp.schemas import UserUpdate, UserCreate


class ProfessorBot(Bot):
    def __init__(self, api_key: str):
        super().__init__(api_key, default=DefaultBotProperties())
        self.__users: dict[int, dict] = {}
        self.__logger = logging.getLogger(self.__class__.__name__)

        self.__logs_dir = LOGS_DIR / f"{BOT_NAMES.get(self.id)}"
        self.__logs_dir.mkdir(exist_ok=True)

    @property
    def users(self):
        return self.__users

    @property
    def log(self):
        return self.__logger

    # 🔹 Helper: create/get per-user logger with logs/<name>.txt
    def _get_user_logger(self, name: str) -> logging.Logger:
        logger = logging.getLogger(name)
        logger.setLevel(logging.INFO)

        log_file = self.__logs_dir / f"{name}.txt"

        # avoid adding multiple handlers for same logger
        already_has_file = any(
            isinstance(h, logging.FileHandler)
            and getattr(h, "baseFilename", None)
            and Path(h.baseFilename) == log_file
            for h in logger.handlers
        )
        if not already_has_file:
            fh = logging.FileHandler(log_file, encoding="utf-8")
            fh.setFormatter(logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                "%Y-%m-%d %H:%M:%S"
            ))
            logger.addHandler(fh)

        user_id = int(name)
        if user_id in self.__users:
            self.__users[user_id]["logger"] = logger
        return logger

    # ---------------- LOAD USERS ----------------
    async def load_users(self):
        async with get_session() as session:
            db_users = await get_users(session)

        self.__users = {}
        for user in db_users:
            user_logger = self._get_user_logger(str(user.tg_id))  # 🔹 per-user file logger
            self.__users[user.tg_id] = {**user.to_dict(), "logger": user_logger}

        self.__logger.info(f"Loaded {len(self.__users)} users from DB successfully")

    # ---------------- CREATE USER ----------------
    async def create_user(self, user_id: int, phone: str):
        thread_id = await professor_client.create_thread()
        user_create = UserCreate(tg_id=user_id, tg_phone=phone, thread_id=thread_id)

        async with get_session() as session:
            user = await create_user(session, user_create)

        user_logger = self._get_user_logger(str(user.tg_id))  # 🔹 per-user file logger
        self.__users[user_id] = {**user.model_dump(), "logger": user_logger}

        self.__logger.info(f"Created new user: {user_id}, phone={phone}")
        return thread_id

    # ---------------- PARSE RESPONSE ----------------
    async def parse_response(self, response: dict, message: Message):
        user_id = message.from_user.id

        # 🔹 Resolve logger for this user (fallback to global)
        user_data = self.__users.get(user_id)
        logger: logging.Logger = user_data["logger"] if user_data and "logger" in user_data else self._get_user_logger(user_id)

        # 🔹 Log incoming message
        logger.info(
            "INCOMING message | user_id=%s | text=%r",
            user_id,
            getattr(message, "text", None)
        )

        files: list[str] = response.get("files") or []
        text: str = (response.get("text") or "").strip()
        input_tokens: int = int(response.get("input_tokens") or 0)
        output_tokens: int = int(response.get("output_tokens") or 0)

        logger.info(
            "MODEL RESPONSE (raw) | user_id=%s | files=%d | text_len=%d | input_tokens=%d | output_tokens=%d",
            user_id,
            len(files),
            len(text),
            input_tokens,
            output_tokens,
        )

        # 🔹 Detect blocking command
        match = re.search(r"BLOCK_USER_TG_(\d+)", text, re.IGNORECASE)
        if match:
            days = int(match.group(1))
            text = re.sub(r"BLOCK_USER_TG_\d+", "", text, flags=re.IGNORECASE).strip()
            blocked_until = datetime.now() + timedelta(days=days) if days > 0 else datetime.max

            logger.warning(
                "Blocking user for %s days (until %s)", days, blocked_until
            )

            async with get_session() as session:
                await update_user(session, user_id, UserUpdate(blocked_until=blocked_until))
            if user_id in self.__users:
                self.__users[user_id]["blocked_until"] = blocked_until

        # 🔹 Update token usage
        if input_tokens or output_tokens:
            prev_input = self.__users.get(user_id, {}).get("input_tokens", 0)
            prev_output = self.__users.get(user_id, {}).get("output_tokens", 0)
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

            async with get_session() as session:
                await update_user(
                    session,
                    user_id,
                    UserUpdate(input_tokens=new_input, output_tokens=new_output),
                )

            if user_id in self.__users:
                self.__users[user_id]["input_tokens"] = new_input
                self.__users[user_id]["output_tokens"] = new_output

            self.__logger.info(
                f"Updated tokens for {user_id}: +{input_tokens}/{output_tokens} "
                f"(total {new_input}/{new_output})"
            )

        # 🔹 Handle empty
        if not files and not text:
            logger.warning("EMPTY response (no files, no text)")
            return await message.answer("oshibochka vishla da")

        # 🔹 Handle files
        if files:
            logger.info("OUTGOING response has %d file(s)", len(files))
            if len(files) == 1:
                caption = re.sub(r"【[^】]*】", "", text[:1024]) or None
                logger.info(
                    "OUTGOING single photo | caption_len=%d",
                    len(caption or ""),
                )
                return await message.answer_photo(
                    FSInputFile(files[0]),
                    caption=caption,
                )
            else:
                media = [InputMediaPhoto(media=FSInputFile(f)) for f in files]
                if text:
                    media[0].caption = re.sub(r"【[^】]*】", "", text[:1024])
                logger.info(
                    "OUTGOING media group | first_caption_len=%d",
                    len(media[0].caption or ""),
                )
                return await message.answer_media_group(media)

        # 🔹 Handle long text
        if len(text) > MAX_TG_MSG_LEN:
            logger.info("OUTGOING long text | len=%d | splitting", len(text))
            chunks = await split_text(text)
            for idx, chunk in enumerate(chunks, start=1):
                clean_chunk = re.sub(r"【[^】]*】", "", chunk)
                logger.info(
                    "OUTGOING chunk %d/%d | len=%d",
                    idx,
                    len(chunks),
                    len(clean_chunk),
                )
                await message.answer(
                    clean_chunk,
                    parse_mode=None,
                    reply_markup=ReplyKeyboardRemove(),
                )
            return None

        # 🔹 Normal text
        clean_text = re.sub(r"【[^】]*】", "", text)
        logger.info(
            "OUTGOING text | len=%d | preview=%r",
            len(clean_text),
            clean_text[:200],
        )
        return await message.answer(
            clean_text,
            parse_mode=None,
            reply_markup=ReplyKeyboardRemove(),
        )


professor_bot = ProfessorBot(AI_BOT_TOKEN)
dose_bot = ProfessorBot(AI_BOT_TOKEN2)
new_bot = ProfessorBot(AI_BOT_TOKEN3)

professor_client = ProfessorClient()
dose_client = ProfessorClient(OPENAI_API_KEY2, ASSISTANT_ID2)
new_client = ProfessorClient(OPENAI_API_KEY2, ASSISTANT_ID3)

professor_dp = Dispatcher(storage=MemoryStorage())
professor_dp.include_routers(professor_user_router, professor_admin_router)
professor_dp.message.middleware(ContextMiddleware(professor_bot, professor_client))
professor_dp.callback_query.middleware(ContextMiddleware(professor_bot, professor_client))

dose_dp = Dispatcher(storage=MemoryStorage())
dose_dp.include_routers(dose_user_router, dose_admin_router)
dose_dp.message.middleware(ContextMiddleware(dose_bot, dose_client))
dose_dp.callback_query.middleware(ContextMiddleware(dose_bot, dose_client))

new_dp = Dispatcher(storage=MemoryStorage())
new_dp.include_routers(new_user_router, new_admin_router)
new_dp.message.middleware(ContextMiddleware(new_bot, new_client))
new_dp.callback_query.middleware(ContextMiddleware(new_bot, new_client))


async def run_professor_bot():
    await professor_bot.delete_webhook(drop_pending_updates=False)
    await professor_bot.load_users()
    await professor_dp.start_polling(professor_bot)


async def run_dose_bot():
    await dose_bot.delete_webhook(drop_pending_updates=False)
    await dose_bot.load_users()
    await dose_dp.start_polling(dose_bot)


async def run_new_bot():
    await new_bot.delete_webhook(drop_pending_updates=False)
    await new_bot.load_users()
    await new_dp.start_polling(new_bot)
