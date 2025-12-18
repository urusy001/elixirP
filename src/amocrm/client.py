from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

import httpx
from datetime import datetime, timedelta, UTC
from urllib.parse import urlparse, parse_qs
from playwright.async_api import async_playwright

from src.helpers import normalize_address_for_cf
from config import (
    AMOCRM_CLIENT_ID,
    AMOCRM_CLIENT_SECRET,
    AMOCRM_ACCESS_TOKEN,
    AMOCRM_LOGIN_EMAIL,
    AMOCRM_LOGIN_PASSWORD,
    AMOCRM_REFRESH_TOKEN,
    AMOCRM_REDIRECT_URI,
    AMOCRM_BASE_DOMAIN, WORKING_DIR,
)

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
        self.STATUS_IDS = {
            "main": 81419122,
            "check_paid": 75784946,
            "packaged": 75784942,
            "package_sent": 76566302,
            "package_delivered": 76566306,
            "won": 142
        }
        self.PIPELINE_ID = 9280278
        self.CF = {
            "cdek_tracking_url": 752437,
            "delivery_cdek": 752921,
            "consultant_call": 753605,
            "delivery_yandex": 753603,
            "tg_nick": 753183,
            "payment": 753401,
            "cdek_number": 751951,
            "city": 752927,
            "address": 752435,
            "promo_code": 752923,
            "delivery_sum": 752929,
            "ai": 753181,
        }
        
        self.logger = logging.getLogger(self.__class__.__name__)
        self.base_domain = base_domain
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.expires_at = datetime.now(UTC) + timedelta(days=1)

    # ---------- TOKEN MANAGEMENT ----------
    @property
    def COMPLETE_STATUS_IDS(self):
        x = list(self.STATUS_IDS.values())
        x.remove(self.STATUS_IDS["main"])
        return x

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

            await page.wait_for_url(
                "https://elixirpeptides.devsivanschostakov.org/webhooks/amocrm*",
                timeout=30000,
            )
            url = page.url
            await browser.close()

        code = parse_qs(urlparse(url).query).get("code", [None])[0]
        if not code:
            raise RuntimeError("Failed to extract AUTH_CODE from redirect URL.")
        self.logger.info("✅ Got new AUTH_CODE")
        return code

    def _save_tokens_to_env(self, access_token: str, refresh_token: str):
        """Persist updated tokens to .env for future runs."""
        path = os.path.join(WORKING_DIR, ".env")
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
            if res.text.strip(): return res.json()
            return {}

    async def get(self, endpoint: str, **kwargs):
        return await self._request("GET", endpoint, **kwargs)

    async def post(self, endpoint: str, **kwargs):
        return await self._request("POST", endpoint, **kwargs)

    async def patch(self, endpoint: str, **kwargs):
        return await self._request("PATCH", endpoint, **kwargs)

    async def delete(self, endpoint: str, **kwargs):
        return await self._request("DELETE", endpoint, **kwargs)

    async def create_lead(
            self,
            name: str,
            status_id: int,
            price: int | None = None,
            custom_fields: dict[int, object] | None = None,
            responsible_user_id: int | None = None,

    ):
        """
        Create a single lead in AmoCRM.
        - name: lead title, e.g. "Заказ №123"
        - price: deal amount in рублях
        - custom_fields: {field_id: value} (value cast to string)
        - responsible_user_id: Amo user id (optional)
        """
        body_lead: dict = {
            "name": name,
            "pipeline_id": self.PIPELINE_ID,
            "status_id": status_id,
        }

        if price is not None:
            body_lead["price"] = price

        if responsible_user_id is not None:
            body_lead["responsible_user_id"] = responsible_user_id

        if custom_fields:
            cf_list: list[dict] = []
            for field_id, value in custom_fields.items():
                if value is None:
                    continue
                cf_list.append(
                    {
                        "field_id": field_id,
                        "values": [{"value": str(value)}],
                    }
                )
            if cf_list:
                body_lead["custom_fields_values"] = cf_list

        payload = [body_lead]
        data = await self.post("/api/v4/leads", json=payload)
        return data["_embedded"]["leads"][0]

    async def add_lead_note(self, lead_id: int, text: str):
        payload = [
            {
                "entity_id": lead_id,
                "note_type": "common",
                "params": {"text": text},
            }
        ]
        return await self.post("/api/v4/leads/notes", json=payload)

    # ---------- INTERNAL: ADDRESS NORMALIZATION FOR CF ----------

    async def create_lead_with_contact_and_note(
            self,
            lead_name: str,
            price: int,
            address_str: str,
            phone: str,
            email: str | None,
            order_number: str,
            delivery_service: str,
            note_text: str,
            payment_method: str,
            tg_nick: str | None = '',
            status_id: int = None,
            delivery_sum: float | int | None = None,
    ):
        """
        1) Create lead with custom fields
        2) Create contact (phone/email)
        3) Link contact to lead
        4) Add note to lead

        Returns dict: {"lead": lead_dict, "contact": contact_dict}
        """
        lead_custom_fields: dict[int, object] = {}
        if address_str: lead_custom_fields[self.CF["address"]] = address_str
        if tg_nick: lead_custom_fields[self.CF["tg_nick"]] = tg_nick
        if delivery_sum: lead_custom_fields[self.CF["delivery_sum"]] = delivery_sum
        if delivery_service.upper() == "CDEK":
            lead_custom_fields[self.CF["delivery_cdek"]] = "СДЭК"
            lead_custom_fields[self.CF["cdek_number"]] = order_number
            lead_custom_fields[self.CF["cdek_tracking_url"]] = f'https://www.cdek.ru/ru/tracking/?order_id={order_number}'

        elif delivery_service.upper() == "YANDEX": lead_custom_fields[self.CF["delivery_yandex"]] = "Яндекс"
        lead_custom_fields[self.CF["payment"]] = payment_method

        lead = await self.create_lead(
            name=f"Заказ №{order_number} с Приложения ТГ",
            price=price,
            custom_fields=lead_custom_fields,
            status_id=status_id or self.STATUS_IDS["main"]
        )
        lead_id = lead["id"]

        contact_body: dict = {
            "name": lead_name,
            "custom_fields_values": [],
        }

        if phone:
            contact_body["custom_fields_values"].append(
                {
                    "field_code": "PHONE",
                    "values": [{"value": phone, "enum_code": "WORK"}],
                }
            )

        if email:
            contact_body["custom_fields_values"].append(
                {
                    "field_code": "EMAIL",
                    "values": [{"value": email, "enum_code": "WORK"}],
                }
            )

        contacts_payload = [contact_body]
        contacts_res = await self.post("/api/v4/contacts", json=contacts_payload)
        contact = contacts_res["_embedded"]["contacts"][0]
        contact_id = contact["id"]

        link_payload = [
            {
                "to_entity_id": contact_id,
                "to_entity_type": "contacts",
            }
        ]
        await self.post(f"/api/v4/leads/{lead_id}/link", json=link_payload)
        await self.add_lead_note(lead_id, note_text)

        return True

    async def get_main_pipeline_statuses(self) -> dict[str, int]:
        """
        Получить все статусы основного пайплайна (self.PIPELINE_ID).

        Возвращает словарь:
        {
            "Новый лид": 123456,
            "В работе": 123457,
            ...
        }
        """
        data = await self.get(f"/api/v4/leads/pipelines/{self.PIPELINE_ID}/statuses")

        embedded = data.get("_embedded", {})
        statuses = embedded.get("statuses", [])

        result: dict[str, int] = {}
        for st in statuses:
            name = st.get("name")
            sid = st.get("id")
            if name and sid is not None:
                result[name] = sid

        return result

    async def get_valid_deal(self, code: str | int) -> int | None:
        """
        EXACT match rule:
          - lead name contains '№{code}<SPACE>' (space required right after the code)
          - lead status_id in COMPLETE_STATUS_IDS

        Returns lead price (int) or None.
        """
        code_str = str(code).strip()

        # exact token: №code + space
        needle = f"№{code_str} "
        # strict regex: same thing, but robust + explicit whitespace
        rx = re.compile(rf"№{re.escape(code_str)}\s")

        page = 1
        limit = 50
        max_pages = 20  # safety

        while page <= max_pages:
            data = await self.get(
                "/api/v4/leads",
                params={
                    # use the exact needle to reduce noise,
                    # but still DO NOT trust it for exactness
                    "query": needle,
                    "limit": limit,
                    "page": page,
                },
            )

            leads = (data.get("_embedded") or {}).get("leads") or []
            if not leads:
                return None

            for lead in leads:
                name = lead.get("name") or ""
                status_id = lead.get("status_id")

                # ✅ exact match on your side (prevents №{code}1121, etc.)
                if status_id in self.COMPLETE_STATUS_IDS and rx.search(name):
                    price = lead.get("price", None)
                    if 'ElixirPeptide' in name and not price: return "old"
                    else: return int(price) if price else None

# ---------- INSTANCE ----------
amocrm = AsyncAmoCRM(
    base_domain=AMOCRM_BASE_DOMAIN,
    client_id=AMOCRM_CLIENT_ID,
    client_secret=AMOCRM_CLIENT_SECRET,
    redirect_uri=AMOCRM_REDIRECT_URI,
    access_token=AMOCRM_ACCESS_TOKEN,
    refresh_token=AMOCRM_REFRESH_TOKEN,
)
