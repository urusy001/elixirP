from __future__ import annotations

import logging
from datetime import datetime

from openai import AsyncClient

from src.ai.eventhandler import ProfessorEventHandler


class ProfessorClient(AsyncClient):
    def __init__(self, api_key: str, assistant_id: str | None = None, *args, **kwargs):
        super().__init__(api_key=api_key, *args, **kwargs)
        self.__logger = logging.getLogger(self.__class__.__name__)
        self.__assistant_id = assistant_id or ""

    def _sync_usage_from_final_run(self, final_run, event_handler: ProfessorEventHandler) -> None:
        usage = getattr(final_run, "usage", None)
        if not usage:
            return
        prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
        completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
        event_handler.response["input_tokens"] = max(event_handler.response["input_tokens"], prompt_tokens)
        event_handler.response["output_tokens"] = max(event_handler.response["output_tokens"], completion_tokens)

    async def _recover_response_if_empty(self, thread_id: str, stream, event_handler: ProfessorEventHandler) -> None:
        if event_handler.has_payload():
            return

        final_messages = []
        try:
            final_messages = await stream.get_final_messages()
        except RuntimeError:
            self.__logger.warning("No final messages found in stream snapshot.")

        for message in final_messages:
            if getattr(message, "role", None) == "assistant":
                await event_handler.ingest_message(message, source="final_messages_snapshot")

        if event_handler.has_payload():
            return

        run_steps = []
        try:
            run_steps = await stream.get_final_run_steps()
        except RuntimeError:
            self.__logger.warning("No run steps found for fallback parsing.")

        if run_steps:
            step_summary = ", ".join(
                f"{step.id}:{getattr(getattr(step, 'step_details', None), 'type', 'unknown')}:{getattr(step, 'status', 'unknown')}"
                for step in run_steps
            )
            self.__logger.info("Run steps summary: %s", step_summary)

        message_ids: list[str] = []
        for step in run_steps:
            details = getattr(step, "step_details", None)
            if getattr(details, "type", None) != "message_creation":
                continue
            message_id = getattr(getattr(details, "message_creation", None), "message_id", None)
            if message_id:
                message_ids.append(message_id)

        if not message_ids:
            return

        self.__logger.warning("Recovering assistant output from message_creation steps: %s", message_ids)
        for message_id in message_ids:
            try:
                message = await self.beta.threads.messages.retrieve(message_id=message_id, thread_id=thread_id)
            except Exception as exc:
                self.__logger.warning("Failed to retrieve assistant message %s: %s", message_id, exc)
                continue

            if getattr(message, "role", None) == "assistant":
                await event_handler.ingest_message(message, source="run_step_message_creation")

    async def create_thread(self):
        thread = await self.beta.threads.create()
        return thread.id

    async def send_message(self, message: str, thread_id: str, assistant_id: str):
        """
        Send a message to the assistant with rich context and improved reasoning.
        """
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
        ) as stream:
            await stream.until_done()
            final_run = await stream.get_final_run()
            self.__logger.info(
                "Run completed | id=%s status=%s incomplete_details=%s last_error=%s",
                getattr(final_run, "id", None),
                getattr(final_run, "status", None),
                getattr(final_run, "incomplete_details", None),
                getattr(final_run, "last_error", None),
            )
            self._sync_usage_from_final_run(final_run, event_handler)
            await self._recover_response_if_empty(thread_id, stream, event_handler)

        if not event_handler.has_payload():
            self.__logger.warning(
                "Assistant run produced no text/files after all fallbacks | thread_id=%s assistant_id=%s",
                thread_id,
                assistant_id,
            )
        return event_handler.response

    @property
    def assistant_id(self) -> str: return self.__assistant_id

    @property
    def log(self): return self.__logger
