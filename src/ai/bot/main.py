import re
import logging
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, FSInputFile, InputMediaPhoto, ReplyKeyboardRemove

from config import AI_BOT_TOKEN as TELEGRAM_BOT_TOKEN
from src.ai.client import ProfessorClient
from src.ai.bot.middleware import ContextMiddleware
from src.webapp import get_session
from src.webapp.crud import get_users, create_user, update_user
from src.webapp.schemas import UserUpdate, UserCreate
from src.helpers import split_text, MAX_TG_MSG_LEN
from src.ai.bot.handlers import user_router, admin_router


class ProfessorBot(Bot):
    def __init__(self, api_key: str):
        super().__init__(api_key, default=DefaultBotProperties())
        self.__users: dict[int, dict] = {}
        self.__logger = logging.getLogger(self.__class__.__name__)

    @property
    def users(self):
        return self.__users

    @property
    def log(self):
        return self.__logger

    # ---------------- LOAD USERS ----------------
    async def load_users(self):
        async with get_session() as session:
            db_users = await get_users(session)
        self.__users = {user.tg_id: user.to_dict() for user in db_users}
        self.__logger.info(f"Loaded {len(self.__users)} users from DB successfully")

    # ---------------- CREATE USER ----------------
    async def create_user(self, user_id: int, phone: str):
        from src.ai.client import ProfessorClient  # avoid circular import
        professor_client = ProfessorClient()

        thread_id = await professor_client.create_thread()
        user = UserCreate(tg_id=user_id, tg_phone=phone, thread_id=thread_id)

        async with get_session() as session:
            await create_user(session, user)

        self.__users[user_id] = user.model_dump()
        self.__logger.info(f"Created new user: {user_id}, phone={phone}")
        return thread_id

    # ---------------- PARSE RESPONSE ----------------
    async def parse_response(self, response: dict, message: Message):
        files: list[str] = response.get("files") or []
        text: str = (response.get("text") or "").strip()
        input_tokens: int = int(response.get("input_tokens") or 0)
        output_tokens: int = int(response.get("output_tokens") or 0)

        user_id = message.from_user.id

        # 🔹 Detect blocking command
        match = re.search(r"BLOCK_USER_TG_(\d+)", text, re.IGNORECASE)
        if match:
            days = int(match.group(1))
            text = re.sub(r"BLOCK_USER_TG_\d+", "", text, flags=re.IGNORECASE).strip()
            blocked_until = datetime.now() + timedelta(days=days) if days > 0 else datetime.max

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
            return await message.answer("oshibochka vishla da")

        # 🔹 Handle files
        if files:
            if len(files) == 1:
                return await message.answer_photo(FSInputFile(files[0]), caption=re.sub(r"【[^】]*】", "", text[:1024]) or None)
            else:
                media = [InputMediaPhoto(media=FSInputFile(f)) for f in files]
                if text:
                    media[0].caption = re.sub(r"【[^】]*】", "", text[:1024])
                return await message.answer_media_group(media)

        # 🔹 Handle long text
        if len(text) > MAX_TG_MSG_LEN:
            chunks = await split_text(text)
            for chunk in chunks:
                await message.answer(re.sub(r"【[^】]*】", "", chunk), parse_mode=None, reply_markup=ReplyKeyboardRemove())
            return None

        # 🔹 Normal text
        return await message.answer(re.sub(r"【[^】]*】", "", text), parse_mode=None, reply_markup=ReplyKeyboardRemove())


bot = ProfessorBot(TELEGRAM_BOT_TOKEN)
professor_client = ProfessorClient()
dp = Dispatcher(storage=MemoryStorage())

dp.include_routers(user_router, admin_router)
dp.message.middleware(ContextMiddleware(bot, professor_client))
dp.callback_query.middleware(ContextMiddleware(bot, professor_client))


async def run_bot():
    await bot.delete_webhook(drop_pending_updates=False)
    await bot.load_users()
    await dp.start_polling(bot)
