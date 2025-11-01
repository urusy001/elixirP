import asyncio
import json
import logging
import os

import aiofiles
import httpx

from config import MANAGER_USER, MANAGER_PASS, DATA_DIR
from src.peptides import endpoints

logging.basicConfig(
    level=logging.INFO,  # or INFO, WARNING, ERROR
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)


class AsyncElixirClient(httpx.AsyncClient):
    def __init__(self, username: str, password: str):
        super().__init__(follow_redirects=True, timeout=20)
        self.__auth = (username, password)
        self.__logger = logging.getLogger(self.__class__.__name__)
        print(self.__auth)

    async def authorize(self):
        payload = {
            "login_context": "mgr",
            "modhash": "",
            "returnUrl": "/manager/",
            "username": self.__auth[0],
            "password": self.__auth[1],
            "rememberme": "1",
            "login": "1",
        }

        resp = await self.post(endpoints.LOGIN, data=payload)

        # Real success detection: check for MODX session cookies
        cookies = list(self.cookies.keys())
        if any("PHPSESSID" in c or "modx" in c.lower() for c in cookies):
            self.__logger.info(f"✅ Login successful.: {resp.text}")
            return True

        self.__logger.error("❌ Login failed, got login page again.")
        self.__logger.debug(resp.text[:400])
        return False

    async def get_reviews(self, kwargs: dict | None = None):
        """Fetch reviews JSON with an already logged-in client."""
        resp = await self.get(f'{endpoints.REVIEWS}/get.json?email=sobaka_sam007@mail.ru')
        if resp.status_code != 200:
            self.__logger.info(f"Failed to fetch reviews: {resp.text}")
            self.__logger.info(resp.text[:300])
            return None
        try:
            return resp.json()

        except Exception:
            self.__logger.info("⚠️ Non-JSON response:")
            self.__logger.info(resp.text[:300])
            return None


async def main():
    client = AsyncElixirClient(MANAGER_USER, MANAGER_PASS)
    await client.authorize()
    data = await client.get_reviews()
    async with aiofiles.open(os.path.join(DATA_DIR, "xreviews.json"), mode="w", encoding='utf-8') as f:
        await f.write(json.dumps(data, indent=4, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
