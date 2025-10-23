import json
import asyncio
import logging

import httpx
from cdek.api import CDEKClient
from fastapi import HTTPException

from config import CDEK_ACCOUNT, CDEK_SECURE_PASSWORD, CDEK_API_URL

async def get_access_token(base_url: str | None = CDEK_API_URL, account: str | None = CDEK_ACCOUNT, secure_password: str | None = CDEK_SECURE_PASSWORD) -> str:
    async with httpx.AsyncClient(timeout=10) as httpx_client:
        resp = await httpx_client.post(
            f"{base_url}/oauth/token",
            params={
                "grant_type": "client_credentials",
                "client_id": account,
                "client_secret": secure_password,
            },
        )
        data = resp.json()
        if "access_token" not in data:
            raise HTTPException(status_code=500, detail="Failed to obtain CDEK token")
        return data["access_token"], data["expires_in"]

class CDEKClientV2(CDEKClient):
    def __init__(self, account: str | None = CDEK_ACCOUNT, secure_password: str | None = CDEK_SECURE_PASSWORD):
        super().__init__(account, secure_password)
        self.base_url = CDEK_API_URL
        self._access_token: str | None = None
        self.log = logging.getLogger(self.__class__.__name__)

    async def token_worker(self):
        while True:
            token, delay = await get_access_token(self.base_url, self._account, self._secure_password)
            self._access_token = token
            await asyncio.sleep(delay)

client = CDEKClientV2(CDEK_ACCOUNT, CDEK_SECURE_PASSWORD)
