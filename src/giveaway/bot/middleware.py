from typing import Callable, Awaitable, Any
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject


class GiveawayMiddleware(BaseMiddleware):
    def __init__(self, bot_instance):
        super().__init__()
        self.bot_instance = bot_instance

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any]
    ):
        # Inject into handler's data
        data['giveaway_bot'] = self.bot_instance
        return await handler(event, data)
