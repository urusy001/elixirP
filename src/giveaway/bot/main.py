import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode, ChatMemberStatus
from aiogram.fsm.storage.memory import MemoryStorage

from config import PRIZEDRAW_BOT_TOKEN as TELEGRAM_BOT_TOKEN
from src.giveaway.bot.handlers import user_router, admin_router
from src.giveaway.bot.middleware import GiveawayMiddleware


class GiveawayBot(Bot):
    def __init__(self, api_key: str | None = TELEGRAM_BOT_TOKEN):
        super().__init__(api_key, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        self.__logger = logging.getLogger(self.__class__.__name__)

    @property
    def log(self):
        return self.__logger

    async def is_channel_admin(self, channel_username: str) -> bool:
        try:
            me = await self.get_me()
            member = await self.get_chat_member(chat_id=f'@{channel_username}', user_id=me.id)
            return member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR)
        except Exception as e:
            self.__logger.error(f"Error checking bot admin rights: {e}")
            return False

    async def is_user_subscribed(self, user_id: int, channel_username: str) -> bool:
        try:
            member = await self.get_chat_member(chat_id=f'@{channel_username}', user_id=user_id)
            return member.status in (
                ChatMemberStatus.MEMBER,
                ChatMemberStatus.CREATOR,
                ChatMemberStatus.ADMINISTRATOR,
            )
        except Exception as e:
            self.__logger.error(f"Error checking subscription: {e}")
            return False


bot = GiveawayBot()
dp = Dispatcher(storage=MemoryStorage())
dp.include_routers(user_router, admin_router)
dp.message.middleware(GiveawayMiddleware(bot))
dp.callback_query.middleware(GiveawayMiddleware(bot))


async def run_bot():
    await bot.delete_webhook(drop_pending_updates=False)
    await dp.start_polling(bot)
