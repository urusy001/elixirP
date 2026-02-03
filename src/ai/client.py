from __future__ import annotations

import logging
from datetime import datetime
from openai import AsyncClient

from src.ai.eventhandler import ProfessorEventHandler


class ProfessorClient(AsyncClient):
    def __init__(self, api_key: str, *args, **kwargs):
        super().__init__(api_key=api_key)
        self.__logger = logging.getLogger(self.__class__.__name__)

    async def create_thread(self):
        thread = await self.beta.threads.create()
        return thread.id

    async def send_message(self, message: str, thread_id: str, assistant_id: str):
        """
        Send a message to the assistant with rich context and improved reasoning.
        """
        print(assistant_id)
        self.__logger.info('Запрос: %s', message)
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        system_context = (
            "Ты — умный, внимательный и детальный ассистент—профессор. "
            "Дай ответ с подробными объяснениями, структурой и примерами, "
            "если уместно. БАЗИРУЙ СВОИ ОТВЕТЫ НА ИНФОРМАЦИИ ИЗ ВЕКТОРНОГО ХРАНИЛИЩА только потом сети\n"
            f"Текущее время: {current_time}."
            f"ОБРАЩАЙСЯ СО МНОЙ ТОЛЬКО НА ВЫ"
        )

        event_handler = ProfessorEventHandler(self)
        await self.beta.threads.messages.create(thread_id=thread_id, role="user", content="ОБРАЩАЙСЯ СО МНОЙ ТОЛЬКО НА ВЫ, Пожалуйста, проверь базу знаний перед тем как ответить. ИНАЧЕ ТВОИ ОТВЕТЫ ПРИВЕДУТ К НЕОБРАТИМЫМ ПОСЛЕДСТВИЯМ. в ответах НЕ ГОВОРИ что-то по типу /согласно базе знаний, я проверил базу знаний/, итп")
        await self.beta.threads.messages.create(thread_id=thread_id, role="user", content=message)

        async with self.beta.threads.runs.stream(
            assistant_id=assistant_id,
            event_handler=event_handler,
            thread_id=thread_id,
            additional_instructions=system_context,
            temperature=.3,
            top_p=.15,
            metadata={"origin": "telegram_bot", "lang": "ru"},
        ) as stream: await stream.until_done()
        return event_handler.response

    @property
    def assistant_id(self) -> str: return self.__assistant_id

    @property
    def log(self): return self.__logger
