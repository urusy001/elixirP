from __future__ import annotations

import asyncio
import logging
import os
import re
import secrets
import aiosmtplib
import httpx

from decimal import Decimal
from email.message import EmailMessage
from typing import Optional, Tuple, Literal, Union, Any
from datetime import datetime, timedelta, UTC, timezone
from urllib.parse import urlparse, parse_qs
from playwright.async_api import async_playwright
from sqlalchemy import select

from src.webapp import get_session
from src.webapp.crud import update_cart
from src.webapp.models import Cart
from src.webapp.schemas import CartUpdate

PriceT = Union[int, None, Literal["old"]]

from config import (
    AMOCRM_CLIENT_ID,
    AMOCRM_CLIENT_SECRET,
    AMOCRM_ACCESS_TOKEN,
    AMOCRM_LOGIN_EMAIL,
    AMOCRM_LOGIN_PASSWORD,
    AMOCRM_REFRESH_TOKEN,
    AMOCRM_REDIRECT_URI,
    AMOCRM_BASE_DOMAIN, WORKING_DIR, SMTP_USER, SMTP_PASSWORD,
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
        self.STATUS_WORDS = {
            81419122: "Создан",
            75784938: "Счет отправлен",
            75784946: "Оплачен",
            75784942: "Укомплектован",
            76566302: "Отправлен",
            76566306: "Доставлен",
            74461446: "Ожидание ответа",
            82756582: "Ожидание ответа",
            82657618: "Отменен",
            142: "Завершен",
            143: "Возврат/отказ",
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
    def PAID_STATUS_IDS(self):
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
            if res.status_code != 200: raise RuntimeError(f"Token request failed: {res.status_code} {res.text}")
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
            context = await browser.new_context()
            await context.add_cookies(cookies=[
                {
                    "name": "_fbp",
                    "value": "fb.1.1759897603569.57278834220628747",
                    "domain": ".amocrm.ru",
                    "path": "/",
                    "expires": 1776867450,  # 4/22/2026
                    "httpOnly": False,
                    "secure": False
                },
                {
                    "name": "_ga",
                    "value": "GA1.2.566950930.1759897603",
                    "domain": ".amocrm.ru",
                    "path": "/",
                    "expires": 1803647850,  # 2/26/2027
                    "httpOnly": False,
                    "secure": False
                },
                {
                    "name": "_ga_ZRNBRFQGWK",
                    "value": "GS2.1.s1769109449$o24$g0$t1769109458$j51$l0$h0",
                    "domain": ".amocrm.ru",
                    "path": "/",
                    "expires": 1803647858,  # 2/26/2027
                    "httpOnly": False,
                    "secure": False
                },
                {
                    "name": "_gcl_au",
                    "value": "1.1.1273167476.1769109450",
                    "domain": ".amocrm.ru",
                    "path": "/",
                    "expires": 1776867449,  # 4/22/2026
                    "httpOnly": False,
                    "secure": False
                },
                {
                    "name": "_ym_d",
                    "value": "1759897605",
                    "domain": ".amocrm.ru",
                    "path": "/",
                    "expires": 1791415604,  # 10/7/2026
                    "httpOnly": False,
                    "secure": False
                },
                {
                    "name": "_ym_uid",
                    "value": "1759897605544998924",
                    "domain": ".amocrm.ru",
                    "path": "/",
                    "expires": 1791415604,  # 10/7/2026
                    "httpOnly": False,
                    "secure": False
                },
                {
                    "name": "access_token",
                    "value": "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiIsImp0aSI6Ijg5ZTMxMzBkYTAyYTYzZGVmODA3MmEyYjUzYTA5ZDQ1ZTdjM2YyN2RjNDgyNGJmMzIwNDZmOTUxYTVmZTA2MmE5NzM5OWYyMzc5ZDY3Mzk1In0.eyJhdWQiOiI3YjQ5MGYxOC0yYmU1LTRhNTUtYTc0ZS0xOTYzYzk2NDFiOTgiLCJqdGkiOiI4OWUzMTMwZGEwMmE2M2RlZjgwNzJhMmI1M2EwOWQ0NWU3YzNmMjdkYzQ4MjRiZjMyMDQ2Zjk1MWE1ZmUwNjJhOTczOTlmMjM3OWQ2NzM5NSIsImlhdCI6MTc3MDI1NTEyOSwibmJmIjoxNzcwMjU1MTI5LCJleHAiOjE3NzAyNTc1MjksInN1YiI6IjI0Mjc5ODUiLCJncmFudF90eXBlIjoiIiwiYWNjb3VudF9pZCI6MCwiYmFzZV9kb21haW4iOm51bGwsInZlcnNpb24iOjEsInNjb3BlcyI6WyJjaGF0cyIsImNybSIsIm1haWwiLCJub3RpZmljYXRpb25zIiwidW5zb3J0ZWQiXSwiaGFzaF91dWlkIjoiY2VkODQ3ODktYjkyYy00ZWY3LWJjN2EtNWIyMTBlMDdiYzM2IiwidXNlcl9mbGFncyI6MH0.V4j3Y_VGQyV2jxytZGCRZw-wIMTDpVjf7wmRg8iFSxZD3xEHUlUNVmPc9DYcd_dTgsCfZM0QsnKrw5EAV3I3YGfyTEpYspPgPGLt3V1mNbI_9BcXHX1a0OPD_CXXrXKx7Ln08fqGWXqA2rkD1LDhikNZwZLGQZpnbiIuUjXeqdzTYj1_awBqtzUK_1EGz3tUGvo6gpbO7BvCi6T2oPqcq-19hTt5K3BToFdFHlKp04MvHdz3ejR7s5t0aBoM82Fj4lAIMWL9cUigeLdRzmzhzbldSTEKKRUSOOXmc15V_Y4YFP2JEPNEonyTjBatsv-VuJnFkXrfuYTRog3Sgmdc8g",
                    "domain": ".amocrm.ru",
                    "path": "/",
                    "expires": 1770235929,  # 2/4/2026
                    "httpOnly": True,
                    "secure": True
                },
                {
                    "name": "amo-livechat-id",
                    "value": "Y3ce7H94KPv39OSL47R1x",
                    "domain": "www.amocrm.ru",
                    "path": "/",
                    "expires": 1791415608,  # 10/7/2026
                    "httpOnly": False,
                    "secure": False
                },
                {
                    "name": "csrf_token",
                    "value": "def5020025892cd15576bf06b65f9892f1f0054ea49949b693b722464928826663aa1205da6bb8718edc7759e1c80187cecff43915f73cd9377f6447e1dc4291e99613c0f2a7705781e86343a22f915e1810a3af9e08084e0d60ad3e85f802c2ed648a792e447cc92f77a96cb7697286dffbf8150ab2be6dc97836a32f1b44d2b2e42c5d8d0d8de5de7ea6c99e587ea5ab9f5bd6059a819580efd36e05c3ca6c2be5954f9e332168ac117d40991a53fc57927563e7248f31986e03058a74336c1cc4f13886fdf0effbfd5e770d5bf5522ab8dd5ff315a00ef9db672198f085b55232228d65d12fcafc26ecea68ac3cb97e8f415d90a6e68467466e685fe547ac1bab8e60247ef538cb54c2",
                    "domain": ".www.amocrm.ru",
                    "path": "/",
                    "httpOnly": True,
                    "secure": True,
                    "sameSite": "Lax"
                },
                {
                    "name": "gso_visitor_uid",
                    "value": "2286d211-1cc8-46c4-ac94-97ce4b68e5df",
                    "domain": ".amocrm.ru",
                    "path": "/",
                    "expires": 1794436005,  # 11/11/2026
                    "httpOnly": False,
                    "secure": True
                },
                {
                    "name": "refresh_token",
                    "value": "def5020070b6f95d6099e30e579f80fb41d8f3d1b7ec19b7a09a62e4155bed0b8ae8e07926f623914e6d67fc34d0b2f201c402883d0213429797b3ad040c317a1c312dc2be2c602b425bd205af1376b3dc05794bdb82e9daf7b3a23607512b95486d26c3a6e3f26b618eb29c8981fff03623b7ad970e8e707210a78083f5604525b83120ece90cd797fab89e02bf9659ccf9bba075522d53eea1858cad7bf65b2a7f156dc84c24936a7a9d442a68d8960b90366e7d7e0a3a927f890bc9b616c6cb6d288147cfde0413ee65b5b290cbe8eb8c8f926ebdb2f98d35aeb8ed3e37683c92509872c2d763a33e97c708db14535f35b3d10adec39cb073638143911166ec206735d4347a4bbb219d481837bf9e120fd0659ddf27f5fd1e41bef4fab2219fa11a23b4e4440fc708d69e0fee33261ab0257dff0809ed5a53e5c0e005d328cb6a85883b4cd9794066736517a8ae9c89a50925c75851601a52a8658ae12ca46469ea7b2bc4d7f8bfceb283b83b89dd28a8e5e6706da7b2350727d014c051af1b99ea0edcacd12257f13d8ceb9b49bc31325f3e8107282d918c05334073b9ffc5debad159752aa6772ad06ac857be0e00f45e9f378105c300c341c1d098de650facfc63c8024057c625e87008e6e474eb10486f",
                    "domain": ".amocrm.ru",
                    "path": "/",
                    "expires": 1777926729,  # 5/4/2026
                    "httpOnly": True,
                    "secure": True
                },
                {
                    "name": "sbjs_current",
                    "value": "typ%3Dorganic%7C%7C%7Csrc%3Dgoogle%7C%7C%7Cmdm%3Dorganic%7C%7C%7Ccmp%3D%28none%29%7C%7C%7Ccnt%3D%28none%29%7C%7C%7Ctrm%3D%28none%29",
                    "domain": ".amocrm.ru",
                    "path": "/",
                    "expires": 1800191849,  # 1/17/2027
                    "httpOnly": False,
                    "secure": False
                },
                {
                    "name": "sbjs_current_add",
                    "value": "fd%3D2025-12-20%2019%3A32%3A19%7C%7C%7Cep%3Dhttps%3A%2F%2Fwww.amocrm.ru%2Fsupport%2Fdigitalpipeline%2Ftrigger_webhook%7C%7C%7Crf%3Dhttps%3A%2F%2Fwww.google.com%2F",
                    "domain": ".amocrm.ru",
                    "path": "/",
                    "expires": 1797363139,  # 12/15/2026
                    "httpOnly": False,
                    "secure": False
                },
                {
                    "name": "sbjs_first",
                    "value": "typ%3Dorganic%7C%7C%7Csrc%3Dgoogle%7C%7C%7Cmdm%3Dorganic%7C%7C%7Ccmp%3D%28none%29%7C%7C%7Ccnt%3D%28none%29%7C%7C%7Ctrm%3D%28none%29",
                    "domain": ".amocrm.ru",
                    "path": "/",
                    "expires": 1790983603,  # 10/2/2026
                    "httpOnly": False,
                    "secure": False
                },
                {
                    "name": "sbjs_first_add",
                    "value": "fd%3D2025-10-07%2023%3A26%3A43%7C%7C%7Cep%3Dhttps%3A%2F%2Fwww.amocrm.ru%2F%7C%7C%7Crf%3Dhttps%3A%2F%2Fwww.google.com%2F",
                    "domain": ".amocrm.ru",
                    "path": "/",
                    "expires": 1790983603,  # 10/2/2026
                    "httpOnly": False,
                    "secure": False
                },
                {
                    "name": "sbjs_migrations",
                    "value": "1418474375998%3D1",
                    "domain": ".amocrm.ru",
                    "path": "/",
                    "expires": 1790983603,  # 10/2/2026
                    "httpOnly": False,
                    "secure": False
                },
                {
                    "name": "sbjs_udata",
                    "value": "vst%3D22%7C%7C%7Cuip%3D%28none%29%7C%7C%7Cuag%3DMozilla%2F5.0%20%28Macintosh%3B%20Intel%20Mac%20OS%20X%2010_15_7%29%20AppleWebKit%2F605.1.15%20%28KHTML%2C%20like%20Gecko%29%20Version%2F26.2%20Safari%2F605.1.15",
                    "domain": ".amocrm.ru",
                    "path": "/",
                    "expires": 1800191849,  # 1/17/2027
                    "httpOnly": False,
                    "secure": False
                },
                {
                    "name": "server_time",
                    "value": "1770255131",
                    "domain": ".amocrm.ru",
                    "path": "/",
                    "expires": 1770838331,  # 2/11/2026
                    "httpOnly": False,
                    "secure": False
                },
                {
                    "name": "session_id",
                    "value": "g76n5j4oqj62e55gtq8l45qovi2d7jqh",
                    "domain": ".amocrm.ru",
                    "path": "/",
                    "httpOnly": True,
                    "secure": True
                },
                {
                    "name": "tmr_lvid",
                    "value": "e0ca9bdfe56012be0d4ef4ff67fe6618",
                    "domain": ".amocrm.ru",
                    "path": "/",
                    "expires": 1797935850,  # 12/21/2026
                    "httpOnly": False,
                    "secure": False
                },
                {
                    "name": "tmr_lvidTS",
                    "value": "1759897604366",
                    "domain": ".amocrm.ru",
                    "path": "/",
                    "expires": 1797935850,  # 12/21/2026
                    "httpOnly": False,
                    "secure": False
                },
                {
                    "name": "user_lang",
                    "value": "ru",
                    "domain": ".amocrm.ru",
                    "path": "/",
                    "expires": 1804793558,  # 3/11/2027
                    "httpOnly": False,
                    "secure": False
                }
            ])
            page = await context.new_page()
            await page.goto(auth_url)

            try:
                await page.wait_for_selector('input[name="username"]', timeout=5000)
                await page.fill('input[name="username"]', AMOCRM_LOGIN_EMAIL)
                await page.fill('input[name="password"]', AMOCRM_LOGIN_PASSWORD)
                await page.click('button[type="submit"]')
                self.logger.info("🔐 Logged into AmoCRM")
            except Exception:
                self.logger.info("Already logged in (no login form shown).")

            await page.wait_for_selector("select.js-accounts-list", timeout=20000)
            await page.select_option("select.js-accounts-list", value="19843447")
            await page.click("button.js-accept")
            print(await page.content())
            print("✅ Selected Slimpeptide and clicked Разрешить")
            try: await page.wait_for_url(
                "https://elixirpeptides.devsivanschostakov.org/webhooks/amocrm*",
            )
            except:
                await asyncio.sleep(30)
                print(page.url)
            url = page.url
            await browser.close()

        code = parse_qs(urlparse(url).query).get("code", [None])[0]
        if not code: raise RuntimeError("Failed to extract AUTH_CODE from redirect URL.")
        self.logger.info("✅ Got new AUTH_CODE")
        return code

    def _save_tokens_to_env(self, access_token: str, refresh_token: str):
        """Persist updated tokens to .env for future runs."""
        path = os.path.join(WORKING_DIR, ".env")
        lines = []
        if os.path.exists(path):
            with open(path, "r") as f: lines = f.readlines()

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
        if not found_a: new_lines.append(f'AMOCRM_ACCESS_TOKEN="{access_token}"\n')
        if not found_r: new_lines.append(f'AMOCRM_REFRESH_TOKEN="{refresh_token}"\n')

        with open(path, "w") as f:
            f.writelines(new_lines)
        self.logger.info("💾 Saved new tokens to .env")

    async def authorize(self, code: str | None = None):
        """Get tokens using AUTH_CODE (auto-generate via Playwright if missing)."""
        if not code: code = await self._get_new_auth_code()
        return await self.__request_token("authorization_code", code)

    async def refresh(self):
        """Refresh token, auto reauthorize if refresh revoked."""
        try: return await self.__request_token("refresh_token")
        except Exception as e:
            self.logger.error(f"❌ Refresh failed: {e}, retrying with new AUTH_CODE...")
            return await self.authorize()

    async def ensure_token_valid(self):
        """Refresh token if expired."""
        if not self.access_token or datetime.now(UTC) >= self.expires_at: await self.refresh()

    # ---------- HTTP REQUEST WRAPPERS ----------

    async def _request(self, method: str, endpoint: str, **kwargs):
        await self.ensure_token_valid()
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self.access_token}"
        url = f"https://{self.base_domain}{endpoint}"

        async with httpx.AsyncClient() as client:
            res = await client.request(method, url, headers=headers, **kwargs)
            if res.status_code in [401, 403]:
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
            delivery_sum: float | int | Decimal | None = None,
            promo_code: str | None = None,
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
        if delivery_sum: lead_custom_fields[self.CF["delivery_sum"]] = float(delivery_sum)
        if delivery_service.upper() == "CDEK":
            lead_custom_fields[self.CF["delivery_cdek"]] = "СДЭК"
            lead_custom_fields[self.CF["cdek_number"]] = order_number
            lead_custom_fields[
                self.CF["cdek_tracking_url"]] = f'https://www.cdek.ru/ru/tracking/?order_id={order_number}'

        elif delivery_service.upper() == "YANDEX":
            lead_custom_fields[self.CF["delivery_yandex"]] = "Яндекс"
        lead_custom_fields[self.CF["payment"]] = payment_method
        if promo_code: lead_custom_fields[self.CF["promo_code"]] = promo_code

        lead = await self.create_lead(
            name=f"Заказ №{order_number} с Приложения ТГ",
            price=int(price),
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

        return lead

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

    async def get_valid_deal_price_and_email_verification_code_for_ai(
            self,
            code: str | int,
    ) -> Tuple[PriceT, Optional[str], Optional[str]]:
        code_str = str(code).strip()
        needle = f"№{code_str} "
        rx = re.compile(rf"№{re.escape(code_str)}\s")

        # --- NEW: cutoff 2 months ---
        cutoff_ts = int((datetime.now(timezone.utc) - timedelta(days=62)).timestamp())

        page = 1
        limit = 50
        max_pages = 20

        while page <= max_pages:
            data = await self.get(
                "/api/v4/leads",
                params={
                    "query": needle,
                    "limit": limit,
                    "page": page,
                    "with": "contacts",
                },
            )

            leads = (data.get("_embedded") or {}).get("leads") or []
            if not leads: return "not_found", None, None
            for lead in leads:
                name = lead.get("name") or ""
                status_id = lead.get("status_id")
                created_at = lead.get("created_at")
                print(lead, created_at, cutoff_ts)
                if isinstance(created_at, (int, float)) and created_at < cutoff_ts: continue
                elif not isinstance(created_at, (int, float)): continue
                if status_id in self.PAID_STATUS_IDS and rx.search(name):
                    raw_price = lead.get("price", None)
                    if not raw_price: return "old", None, None

                    price = int(raw_price) if raw_price else 0

                    if isinstance(price, (int, float)) and price > 5000:
                        email = await self._extract_lead_email(lead)
                        if not email:
                            return price, None, None

                        verification_code = self._generate_6_digit_code()
                        await self._send_verification_code_email(
                            to_email=email,
                            code=verification_code,
                            deal_code=code_str,
                        )
                        return price, email, verification_code

                    return "low", None, None

            page += 1

        return "not_found", None, None

    @staticmethod
    def _generate_6_digit_code() -> str: return f"{secrets.randbelow(1_000_000):06d}"

    async def _send_verification_code_email(self, to_email: str, code: str, deal_code: str) -> None:
        """
        Sends verification code from Gmail via SMTP.
        Requires:
          self.GMAIL_SMTP_USER (your gmail address)
          self.GMAIL_APP_PASSWORD (Gmail App Password)
          optional: self.GMAIL_FROM_NAME
        """
        from_email = SMTP_USER
        from_name = getattr(self, "GMAIL_FROM_NAME", "ElixirPeptide")

        msg = EmailMessage()
        msg["From"] = f"{from_name} <{from_email}>"
        msg["To"] = to_email
        msg["Subject"] = "Код подтверждения"
        msg.set_content(
            f"""Здравствуйте!
        
Ваш код подтверждения: {code}    
Заказ: №{deal_code}
Если Вы не запрашивали код — свяжитесь с поддержкой.""")

        await aiosmtplib.send(
            msg,
            hostname="smtp.gmail.com",
            port=587,
            start_tls=True,
            username=SMTP_USER,
            password=SMTP_PASSWORD,
            timeout=20,
        )

    async def _extract_lead_email(self, lead: dict) -> Optional[str]:
        """
        Tries to get email from linked contacts:
          1) if lead already contains embedded contact data -> parse it
          2) else fetch /api/v4/contacts/{id} and parse custom_fields_values
        """
        embedded = lead.get("_embedded") or {}
        contacts = embedded.get("contacts") or lead.get("contacts") or []
        if not isinstance(contacts, list) or not contacts: return None
        ordered = sorted(contacts, key=lambda c: 0 if c.get("is_main") else 1)
        for c in ordered:
            if isinstance(c, dict) and c.get("custom_fields_values"):
                email = self._extract_email_from_contact_obj(c)
                if email: return email

            cid = None
            if isinstance(c, dict): cid = c.get("id") or c.get("contact_id")
            if cid:
                contact = await self.get(f"/api/v4/contacts/{cid}")
                email = self._extract_email_from_contact_obj(contact)
                if email: return email

        return None

    async def get_lead_status(self, deal_code: str | int) -> dict[str, Any]:
        """
        Find lead by exact token "№{deal_code}<SPACE>" and return its status info.

        Returns:
          {
            "found": bool,
            "lead_id": int | None,
            "name": str | None,
            "status_id": int | None,
            "status_key": str | None,   # from self.STATUS_IDS reverse map, if known
            "is_complete": bool,
            "price": int | None,
            "pipeline_id": int | None,
          }
        """
        code_str = str(deal_code).strip()
        needle = f"№{code_str} "
        rx = re.compile(rf"№{re.escape(code_str)}\s")
        page = 1
        limit = 50
        max_pages = 20

        while page <= max_pages:
            data = await self.get(
                "/api/v4/leads",
                params={
                    "query": needle,
                    "limit": limit,
                    "page": page,
                },
            )

            leads = (data.get("_embedded") or {}).get("leads") or []
            if not leads: return "Не найден", False
            for lead in leads:
                name = lead.get("name") or ""
                if not rx.search(name): continue
                pipeline_id = lead.get("pipeline_id")
                if pipeline_id is not None and pipeline_id != self.PIPELINE_ID: continue
                status_id = lead.get("status_id")
                is_complete = bool(status_id in self.PAID_STATUS_IDS)
                status_name = self.STATUS_WORDS.get(status_id)
                if status_name is None:
                    self.logger.warning("Unknown amoCRM status_id=%s (lead/deal_code=%s)", status_id, deal_code)
                    status_name = f"UNKNOWN({status_id})"

                return status_name, is_complete
            page += 1

        return "Не найден", False

    @staticmethod
    def _extract_email_from_contact_obj(contact: dict) -> Optional[str]:
        cfs = contact.get("custom_fields_values") or []
        if not isinstance(cfs, list): return None
        for cf in cfs:
            if not isinstance(cf, dict): continue
            code = (cf.get("field_code") or "").upper()
            name = (cf.get("field_name") or "").lower()
            if code == "EMAIL" or "email" in name or "почта" in name:
                values = cf.get("values") or []
                if not isinstance(values, list): continue
                for v in values:
                    val = (v or {}).get("value")
                    if isinstance(val, str) and "@" in val: return val.strip()

        return None

    async def update_lead_status(self, cart_id: str | int):
        status, is_active = await self.get_lead_status(cart_id)
        cart_update = CartUpdate(status=status, is_active=is_active)
        async with get_session() as session: await update_cart(session, cart_id, cart_update)
        self.logger.info(f"Change {cart_id} to {status}")

    async def update_carts(self):
        while True:
            self.logger.info("Started updating carts")
            async with get_session() as session:
                res = await session.execute(select(Cart.id))  # returns column values
                cart_ids = res.scalars().all()  # <-- list[int]

            for cart_id in cart_ids:
                try: await self.update_lead_status(cart_id)
                except Exception:
                    self.logger.exception("Failed to update lead status for cart_id=%s", cart_id)
                    continue
            self.logger.info(f"Finished updating carts: {len(cart_ids)} updated")
            await asyncio.sleep(24 * 60 * 60)


amocrm = AsyncAmoCRM(
    base_domain=AMOCRM_BASE_DOMAIN,
    client_id=AMOCRM_CLIENT_ID,
    client_secret=AMOCRM_CLIENT_SECRET,
    redirect_uri=AMOCRM_REDIRECT_URI,
    access_token=AMOCRM_ACCESS_TOKEN,
    refresh_token=AMOCRM_REFRESH_TOKEN,
)
print(asyncio.run(amocrm.get_main_pipeline_statuses()))