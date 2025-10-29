import asyncio
import json
import logging
import os
from datetime import datetime, timedelta, UTC
from urllib.parse import urlparse, parse_qs

import httpx
from playwright.async_api import async_playwright
from sqlalchemy import select
from dotenv import load_dotenv

from src.webapp.models import Participant

# ------------------- Load environment -------------------
load_dotenv()

AMOCRM_BASE_DOMAIN = os.getenv("AMOCRM_BASE_DOMAIN", "slimpeptide.amocrm.ru")
AMOCRM_CLIENT_ID = os.getenv("AMOCRM_CLIENT_ID")
AMOCRM_CLIENT_SECRET = os.getenv("AMOCRM_CLIENT_SECRET")
AMOCRM_REDIRECT_URI = os.getenv("AMOCRM_REDIRECT_URI")

AMOCRM_ACCESS_TOKEN = os.getenv("AMOCRM_ACCESS_TOKEN")
AMOCRM_REFRESH_TOKEN = os.getenv("AMOCRM_REFRESH_TOKEN")

# Optional credentials for full Playwright auto-login
AMOCRM_LOGIN_EMAIL = os.getenv("AMOCRM_LOGIN_EMAIL")
AMOCRM_LOGIN_PASSWORD = os.getenv("AMOCRM_LOGIN_PASSWORD")


class AsyncAmoCRM:
    def __init__(
        self,
        base_domain: str,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        access_token: str | None = None,
        refresh_token: str | None = None,
    ):
        self.COMPLETE_STATUS_IDS = [75784946, 75784942, 76566302, 76566306, 142]
        self.PIPELINE_ID = 9280278
        self.logger = logging.getLogger(self.__class__.__name__)
        self.base_domain = base_domain
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.expires_at = datetime.now(UTC) + timedelta(days=1)

    # ---------- TOKEN MANAGEMENT ----------

    async def __request_token(self, grant_type: str, code: str | None = None):
        """Request new tokens (either via refresh_token or authorization_code)."""
        url = f"https://{self.base_domain}/oauth2/access_token"
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
            "grant_type": grant_type,
        }
        if grant_type == "authorization_code":
            payload["code"] = code
        elif grant_type == "refresh_token":
            payload["refresh_token"] = self.refresh_token

        print(payload)

        async with httpx.AsyncClient(timeout=30) as client:
            res = await client.post(url, json=payload)
            if res.status_code != 200:
                raise RuntimeError(f"Token request failed: {res.status_code} {res.text}")
            data = res.json()

        self.access_token = data["access_token"]
        self.refresh_token = data["refresh_token"]
        self.expires_at = datetime.now(UTC) + timedelta(seconds=data["expires_in"])
        self._save_tokens_to_env(self.access_token, self.refresh_token)
        self.logger.info("✅ Tokens successfully updated")
        return data

    async def _get_new_auth_code(self) -> str:
        """Use Playwright to log in and authorize the app (get new AUTH_CODE)."""
        auth_url = (
            f"https://www.amocrm.ru/oauth?"
            f"client_id={self.client_id}&redirect_uri={self.redirect_uri}&response_type=code"
        )
        self.logger.warning("🔁 Launching Playwright to get new AUTH_CODE...")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(auth_url)

            # Login if prompted
            try:
                await page.wait_for_selector('input[name="username"]', timeout=5000)
                await page.fill('input[name="username"]', AMOCRM_LOGIN_EMAIL)
                await page.fill('input[name="password"]', AMOCRM_LOGIN_PASSWORD)
                await page.click('button[type="submit"]')
                self.logger.info("🔐 Logged into AmoCRM")
            except Exception:
                self.logger.info("Already logged in (no login form shown).")

            # Select Slimpeptide account
            await page.wait_for_selector("select.js-accounts-list", timeout=20000)
            await page.select_option("select.js-accounts-list", value="19843447")
            await page.click("button.js-accept")
            self.logger.info("✅ Selected Slimpeptide and clicked Разрешить")

            await page.wait_for_url("https://elixirpeptides.devsivanschostakov.org/webhooks/amocrm*", timeout=30000)
            url = page.url
            await browser.close()

        print(url)
        code = parse_qs(urlparse(url).query).get("code", [None])[0]
        if not code:
            raise RuntimeError("Failed to extract AUTH_CODE from redirect URL.")
        self.logger.info("✅ Got new AUTH_CODE")
        return code

    def _save_tokens_to_env(self, access_token: str, refresh_token: str):
        """Persist updated tokens to .env for future runs."""
        path = os.path.join(os.getcwd(), ".env")
        lines = []
        if os.path.exists(path):
            with open(path, "r") as f:
                lines = f.readlines()

        new_lines = []
        found_a, found_r = False, False
        for line in lines:
            if line.startswith("AMOCRM_ACCESS_TOKEN"):
                new_lines.append(f'AMOCRM_ACCESS_TOKEN="{access_token}"\n')
                found_a = True
            elif line.startswith("AMOCRM_REFRESH_TOKEN"):
                new_lines.append(f'AMOCRM_REFRESH_TOKEN="{refresh_token}"\n')
                found_r = True
            else:
                new_lines.append(line)
        if not found_a:
            new_lines.append(f'AMOCRM_ACCESS_TOKEN="{access_token}"\n')
        if not found_r:
            new_lines.append(f'AMOCRM_REFRESH_TOKEN="{refresh_token}"\n')

        with open(path, "w") as f:
            f.writelines(new_lines)
        self.logger.info("💾 Saved new tokens to .env")

    async def authorize(self, code: str | None = None):
        """Get tokens using AUTH_CODE (auto-generate via Playwright if missing)."""
        if not code:
            code = await self._get_new_auth_code()
        return await self.__request_token("authorization_code", code)

    async def refresh(self):
        """Refresh token, auto reauthorize if refresh revoked."""
        try:
            return await self.__request_token("refresh_token")
        except Exception as e:
            self.logger.error(f"❌ Refresh failed: {e}, retrying with new AUTH_CODE...")
            return await self.authorize()

    async def ensure_token_valid(self):
        """Refresh token if expired."""
        if not self.access_token or datetime.now(UTC) >= self.expires_at:
            await self.refresh()

    # ---------- HTTP REQUEST WRAPPERS ----------

    async def _request(self, method: str, endpoint: str, **kwargs):
        await self.ensure_token_valid()
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self.access_token}"
        url = f"https://{self.base_domain}{endpoint}"

        async with httpx.AsyncClient() as client:
            res = await client.request(method, url, headers=headers, **kwargs)

            if res.status_code == 401:
                self.logger.warning("Access token invalid, refreshing...")
                await self.refresh()
                headers["Authorization"] = f"Bearer {self.access_token}"
                res = await client.request(method, url, headers=headers, **kwargs)

            res.raise_for_status()
            if res.text.strip():
                return res.json()
            return {}

    async def get(self, endpoint: str, **kwargs):
        return await self._request("GET", endpoint, **kwargs)

    async def post(self, endpoint: str, **kwargs):
        return await self._request("POST", endpoint, **kwargs)

    async def patch(self, endpoint: str, **kwargs):
        return await self._request("PATCH", endpoint, **kwargs)

    async def delete(self, endpoint: str, **kwargs):
        return await self._request("DELETE", endpoint, **kwargs)

    # ---------- DEAL VALIDATION (your original logic preserved) ----------

    async def get_valid_deal(self, code: str | int, start_date: datetime, session) -> dict:
        code_str = str(code).strip()
        self.logger.info("Checking deal code=%s since=%s", code_str, start_date)

        # 1️⃣ Check if code already in participants
        res = await session.execute(
            select(Participant.deal_code).where(Participant.deal_code == int(code_str))
        )
        existing = res.scalar_one_or_none()
        if existing:
            msg = f"<b>Заказ уже зарегистрирован.</b>\n<i>Код №{code_str} уже есть в базе участников.</i>"
            return {
                "ok": False,
                "reason": "already_registered",
                "details": {"deal_code": code_str},
                "deal": None,
                "html_message": msg,
            }

        # 2️⃣ Fetch leads
        endpoint = f"/api/v4/leads?query=№{code_str}"
        try:
            data = await self.get(endpoint)
        except Exception as e:
            msg = f"<b>Ошибка запроса к AmoCRM:</b> {e}"
            return {
                "ok": False,
                "reason": "api_error",
                "details": {"deal_code": code_str, "error": str(e)},
                "deal": None,
                "html_message": msg,
            }

        leads = data.get("_embedded", {}).get("leads", [])
        if not leads:
            msg = f"<b>Заказ не найден.</b>\n<i>Код №{code_str} отсутствует в AmoCRM.</i>"
            return {
                "ok": False,
                "reason": "not_found",
                "details": {"deal_code": code_str},
                "deal": None,
                "html_message": msg,
            }

        # 3️⃣ Validate
        for lead in leads:
            name = lead.get("name", "").strip().lower().replace("\u00a0", " ")
            pipeline_id = lead.get("pipeline_id", 0)
            status_id = lead.get("status_id", 0)
            if not name.startswith(f"заказ №{code_str}"):
                continue
            if pipeline_id != self.PIPELINE_ID:
                msg = f"<b>Неверная воронка.</b>\n<i>Ожидался pipeline {self.PIPELINE_ID}, найден {pipeline_id}.</i>"
                return {"ok": False, "reason": "pipeline_mismatch", "deal": lead, "html_message": msg}
            if status_id not in self.COMPLETE_STATUS_IDS:
                msg = f"<b>Заказ не завершён.</b>\n<i>Статус {status_id} не завершён.</i>"
                return {"ok": False, "reason": "status_not_complete", "deal": lead, "html_message": msg}

            timestamp = lead.get("closed_at") or lead.get("updated_at") or lead.get("created_at")
            if not timestamp:
                return {"ok": False, "reason": "no_date", "deal": lead, "html_message": "<b>Нет даты заказа.</b>"}

            deal_date = datetime.fromtimestamp(timestamp, UTC)
            if deal_date < start_date:
                msg = f"<b>Слишком старый заказ.</b>\n<i>{deal_date:%d.%m.%Y}, требуется позже {start_date:%d.%m.%Y}</i>"
                return {"ok": False, "reason": "too_old", "deal": lead, "html_message": msg}

            msg = f"<b>Заказ подтверждён!</b>\n<i>Код №{code_str}, завершён {deal_date:%d.%m.%Y}.</i>"
            return {"ok": True, "reason": "ok", "deal": lead, "html_message": msg}

        return {"ok": False, "reason": "no_deals", "html_message": "<b>Не найден подходящий заказ.</b>"}


# ---------- INSTANCE ----------
amocrm = AsyncAmoCRM(
    base_domain=AMOCRM_BASE_DOMAIN,
    client_id=AMOCRM_CLIENT_ID,
    client_secret=AMOCRM_CLIENT_SECRET,
    redirect_uri=AMOCRM_REDIRECT_URI,
    access_token=AMOCRM_ACCESS_TOKEN,
    refresh_token=AMOCRM_REFRESH_TOKEN,
)


# ---------- TEST EXAMPLE ----------
async def save_leads_json():
    now = datetime.now(UTC)
    start_of_week = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    params = {
        "filter[updated_at][from]": int(start_of_week.timestamp()),
        "filter[updated_at][to]": int(now.timestamp()),
    }
    data = await amocrm.get("/api/v4/leads", params=params)
    with open("leads_raw.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("✅ Saved response to leads_raw.json")


if __name__ == "__main__":
    asyncio.run(save_leads_json())