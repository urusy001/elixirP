import os

import aiofiles
import httpx
from openai import AsyncAssistantEventHandler
from openai.types.beta.threads import ImageURLContentBlock, ImageFileContentBlock, TextContentBlock, Message
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

    @override
    async def on_message_done(self, message: Message) -> dict:
        os.makedirs(DOWNLOADS_DIR, exist_ok=True)
        response_text = ""

        files = []

        for content_block in message.content:
            # Text
            if isinstance(content_block, TextContentBlock):
                text = content_block.text.value
                response_text += text
                self.client.log.info(f"Ответ профессора: {text}")

            # Image stored as file on OpenAI
            elif isinstance(content_block, ImageFileContentBlock):
                file_id = content_block.image_file.file_id
                filename = os.path.join(DOWNLOADS_DIR, f"{file_id}.png")
                self.client.log.info(f"Downloading image file from OpenAI: {file_id}")
                content = await self.client.files.content(file_id)
                async with aiofiles.open(filename, "wb") as f:
                    await f.write(content)
                files.append(filename)
                self.client.log.info(f"Saved image file to: {filename}")

            # Image from URL
            elif isinstance(content_block, ImageURLContentBlock):
                url = content_block.image_url.url
                filename = os.path.join(DOWNLOADS_DIR, f"{os.path.basename(url)}.png")
                self.client.log.info(f"Downloading image from URL: {url}")
                async with httpx.AsyncClient() as http:
                    resp = await http.get(url)
                    resp.raise_for_status()
                    async with aiofiles.open(filename, "wb") as f:
                        await f.write(resp.content)
                files.append(filename)
                self.client.log.info(f"Saved image from URL to: {filename}")

        self.client.log.info(f"Message parsing complete. {len(files)} files saved, text length: {len(response_text)}")
        self.response["text"] += response_text
        self.response["files"] += files

    @override
    async def on_run_step_done(self, run_step: RunStep) -> None:
        usage = run_step.usage
        if usage:
            self.response["output_tokens"] += usage.completion_tokens
            self.response["input_tokens"] += usage.prompt_tokens
