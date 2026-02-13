import os

import aiofiles
import httpx
from openai import AsyncAssistantEventHandler
from openai.types.beta.threads import (
    ImageFileContentBlock,
    ImageURLContentBlock,
    Message,
    RefusalContentBlock,
    TextContentBlock,
)
from openai.types.beta.threads.runs import RunStep
from typing_extensions import override

from config import DOWNLOADS_DIR


class ProfessorEventHandler(AsyncAssistantEventHandler):
    def __init__(self, client):
        super().__init__()
        self.response = {
            "text": "",
            "files": [],
            "input_tokens": 0,
            "output_tokens": 0
        }
        self.client = client
        self._parsed_message_ids: set[str] = set()

    def has_payload(self) -> bool:
        return bool((self.response.get("text") or "").strip() or self.response.get("files"))

    async def _download_image_file(self, file_id: str) -> str:
        filename = os.path.join(DOWNLOADS_DIR, f"{file_id}.png")
        self.client.log.info("Downloading image file from OpenAI: %s", file_id)
        content = await self.client.files.content(file_id)
        payload = getattr(content, "content", None)
        if payload is None:
            payload = await content.aread()
        async with aiofiles.open(filename, "wb") as f:
            await f.write(payload)
        self.client.log.info("Saved image file to: %s", filename)
        return filename

    async def _download_image_url(self, url: str) -> str:
        basename = os.path.basename(url.split("?", 1)[0]) or "image"
        filename = os.path.join(DOWNLOADS_DIR, f"{basename}.png")
        self.client.log.info("Downloading image from URL: %s", url)
        async with httpx.AsyncClient() as http:
            resp = await http.get(url)
            resp.raise_for_status()
            async with aiofiles.open(filename, "wb") as f:
                await f.write(resp.content)
        self.client.log.info("Saved image from URL to: %s", filename)
        return filename

    async def ingest_message(self, message: Message, *, source: str) -> None:
        message_id = getattr(message, "id", None)
        if message_id and message_id in self._parsed_message_ids:
            return

        os.makedirs(DOWNLOADS_DIR, exist_ok=True)
        response_text = ""
        files: list[str] = []

        for content_block in message.content or []:
            block_type = getattr(content_block, "type", None)

            if isinstance(content_block, TextContentBlock) or block_type == "text":
                text = getattr(getattr(content_block, "text", None), "value", None) or ""
                response_text += text
                if text:
                    self.client.log.info("Ответ профессора (%s): %s", source, text)
                continue

            if isinstance(content_block, RefusalContentBlock) or block_type == "refusal":
                refusal_text = getattr(content_block, "refusal", None) or ""
                response_text += refusal_text
                if refusal_text:
                    self.client.log.info("Ответ профессора-отказ (%s): %s", source, refusal_text)
                continue

            if isinstance(content_block, ImageFileContentBlock) or block_type == "image_file":
                file_id = getattr(getattr(content_block, "image_file", None), "file_id", None)
                if file_id:
                    files.append(await self._download_image_file(file_id))
                continue

            if isinstance(content_block, ImageURLContentBlock) or block_type == "image_url":
                url = getattr(getattr(content_block, "image_url", None), "url", None)
                if url:
                    files.append(await self._download_image_url(url))
                continue

        self.client.log.info(
            "Message parsing complete (%s). %d files saved, text length: %d",
            source,
            len(files),
            len(response_text),
        )
        self.response["text"] += response_text
        self.response["files"] += files
        if message_id:
            self._parsed_message_ids.add(message_id)

    @override
    async def on_message_done(self, message: Message) -> None:
        await self.ingest_message(message, source="on_message_done")

    @override
    async def on_run_step_done(self, run_step: RunStep) -> None:
        usage = run_step.usage
        if usage:
            self.response["output_tokens"] += int(getattr(usage, "completion_tokens", 0) or 0)
            self.response["input_tokens"] += int(getattr(usage, "prompt_tokens", 0) or 0)
