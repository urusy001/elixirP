from typing import Callable, Awaitable, Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject


class ContextMiddleware(BaseMiddleware):
    def __init__(self, bot_instance, professor_client):
        super().__init__()
        self.bot_instance = bot_instance
        self.professor_client = professor_client

    async def __call__(self, handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]], event: TelegramObject, data: dict[str, Any]):
        data['professor_bot'] = self.bot_instance
        data['professor_client'] = self.professor_client
        return await handler(event, data)
