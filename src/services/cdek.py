from __future__ import annotations

import asyncio
import json
import logging
import time
import httpx
from typing import Any
from fastapi import HTTPException
from config import CDEK_ACCOUNT, CDEK_SECURE_PASSWORD, CDEK_API_URL, CDEK_SENDER_CITY_CODE, CDEK_SENDER_CITY, \
    CDEK_SENDER_POSTAL_CODE, CDEK_SENDER_ADDRESS, CDEK_SENDER_NAME, CDEK_SENDER_PHONE

log = logging.getLogger(__name__)


async def get_access_token(
        base_url: str | None = CDEK_API_URL,
        account: str | None = CDEK_ACCOUNT,
        secure_password: str | None = CDEK_SECURE_PASSWORD,
) -> tuple[str, int]:
    """
    Разовый запрос токена по client_credentials.
    Обычно напрямую не нужен — CDEKClientV2 сам дергает это внутри.
    """
    async with httpx.AsyncClient(timeout=10) as httpx_client:
        resp = await httpx_client.post(
            f"{base_url}/oauth/token",
            params={
                "grant_type": "client_credentials",
                "client_id": account,
                "client_secret": secure_password,
            },
        )

    try:
        resp.raise_for_status()
    except httpx.HTTPError as e:
        log.exception("CDEK OAuth error: %s", resp.text)
        raise HTTPException(
            status_code=502,
            detail={
                "service": "cdek",
                "stage": "oauth",
                "error": str(e),
                "body": resp.text,
            },
        )

    data = resp.json()
    if "access_token" not in data:
        raise HTTPException(status_code=500, detail="Failed to obtain CDEK token")

    token: str = data["access_token"]
    expires_in: int = int(data.get("expires_in", 3600))
    return token, expires_in


class CDEKClientV2:
    """
    Лёгкий асинхронный клиент под CDEK REST API v2.
    Базовый URL должен быть вида 'https://api.cdek.ru/v2'.
    """

    def __init__(
            self,
            account: str | None = CDEK_ACCOUNT,
            secure_password: str | None = CDEK_SECURE_PASSWORD,
            base_url: str | None = CDEK_API_URL,
    ):
        if account is None or secure_password is None:
            raise RuntimeError("CDEK_ACCOUNT and CDEK_SECURE_PASSWORD must be set")

        self._account = account
        self._secure_password = secure_password
        self.base_url = (base_url or "https://api.cdek.ru/v2").rstrip("/")

        self._access_token: str | None = None
        self._token_expires_at: float = 0.0
        self.log = logging.getLogger(self.__class__.__name__)

    # ===================== токен =====================

    async def _ensure_token(self) -> str:
        """
        Возвращает актуальный токен; при необходимости обновляет.
        """
        now = time.time()
        if self._access_token and now < self._token_expires_at - 30:
            return self._access_token

        token, expires_in = await get_access_token(
            base_url=self.base_url,
            account=self._account,
            secure_password=self._secure_password,
        )
        self._access_token = token
        self._token_expires_at = now + float(expires_in)
        self.log.info("CDEK token refreshed, ttl=%s", expires_in)
        return token

    async def token_worker(self) -> None:
        """
        Опциональный фоновой воркер.
        Можно запустить как background task, если хочется держать токен всегда тёплым.
        В обычном сценарии можно вообще не использовать.
        """
        while True:
            token, expires_in = await get_access_token(
                base_url=self.base_url,
                account=self._account,
                secure_password=self._secure_password,
            )
            self._access_token = token
            self._token_expires_at = time.time() + float(expires_in)
            sleep_for = max(float(expires_in) - 30.0, 30.0)
            self.log.info("CDEK token_worker refreshed token, next in %.0fs", sleep_for)
            await asyncio.sleep(sleep_for)

    # ===================== базовый запрос =====================

    async def _request(
            self,
            method: str,
            path: str,
            *,
            params: dict[str, Any] | None = None,
            json: Any | None = None,
    ) -> dict[str, Any]:
        """
        Низкоуровневый метод для вызова CDEK API.
        path должен начинаться с '/', например '/orders'.
        """
        token = await self._ensure_token()
        url = f"{self.base_url}{path}"

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.request(
                method=method.upper(),
                url=url,
                params=params,
                json=json,
                headers=headers,
            )

        if resp.status_code >= 400:
            body = resp.text
            self.log.error("CDEK API error %s %s: %s", method, path, body)
            raise HTTPException(
                status_code=502,
                detail={
                    "service": "cdek",
                    "status_code": resp.status_code,
                    "path": path,
                    "body": body,
                },
            )

        return resp.json()

    # ===================== high-level методы =====================

    async def create_order(self, order: dict[str, Any]) -> dict[str, Any]:
        """
        Создание заказа: POST /v2/orders
        https://apidoc.cdek.ru/#tag/order/operation/register_1
        """
        return await self._request("POST", "/orders", json=order)

    async def get_order_by_uuid(self, uuid: str) -> dict[str, Any]:
        """
        Получение информации о заказе по uuid: GET /v2/orders/{uuid}
        """
        return await self._request("GET", f"/orders/{uuid}")

    async def search_orders(
            self,
            *,
            cdek_number: str | None = None,
            im_number: str | None = None,
    ) -> dict[str, Any]:
        """
        Поиск заказа по номеру CDEK или номеру интернет-магазина.
        GET /v2/orders?cdek_number=... или ?im_number=...
        """
        params: dict[str, Any] = {}
        if cdek_number:
            params["cdek_number"] = cdek_number
        if im_number:
            params["im_number"] = im_number
        return await self._request("GET", "/orders", params=params or None)

    # ===================== helper под твой payload =====================

    @staticmethod
    def build_order_from_payload(
            payload: dict[str, Any],
            order_number: str,
            *,
            sender_city_code: int = CDEK_SENDER_CITY_CODE,
            sender_postal_code: str = CDEK_SENDER_POSTAL_CODE,
            sender_city: str = CDEK_SENDER_CITY,
            sender_address: str = CDEK_SENDER_ADDRESS,
            sender_name: str = CDEK_SENDER_NAME,
            sender_phone: str = CDEK_SENDER_PHONE,
            sender_country_code: str = "RU",
            sender_email: str | None = None,
            delivery_sum: int | float = 295
    ) -> dict[str, Any]:
        """
        Превращает твой checkout-payload в body для POST /v2/orders.

        payload, например:

        {
          "user_id": 7792693628,
          "checkout_data": {...},
          "selected_delivery": {...},
          "selected_delivery_service": "CDEK",
          "contact_info": {...},
          "source": "telegram"
        }
        """
        print(json.dumps(payload, indent=4, ensure_ascii=False))
        checkout = payload["checkout_data"]
        delivery = payload["selected_delivery"]
        contact = payload["contact_info"]
        source = payload.get("source") or "telegram"

        items = checkout["items"]
        total = checkout["total"]

        tariff = delivery["tariff"]
        delivery_mode = delivery["deliveryMode"]   # "office" | "door"
        addr = delivery["address"]

        # ---------- получатель ----------
        first_name = contact.get("name", "").strip()
        last_name = contact.get("surname", "").strip()
        recipient_name = f"{last_name} {first_name}".strip() or first_name or last_name
        recipient_phone = contact["phone"]
        recipient_email = contact.get("email")

        recipient: dict[str, Any] = {
            "name": recipient_name,
            "phones": [{"number": recipient_phone}],
        }
        if recipient_email:
            recipient["email"] = recipient_email

        # ---------- отправитель ----------
        sender: dict[str, Any] = {
            "name": sender_name,
            "phones": [{"number": sender_phone}],
        }
        if sender_email:
            sender["email"] = sender_email

        # ---------- from_location ----------
        from_location: dict[str, Any] = {
            "code": sender_city_code,
            "postal_code": sender_postal_code,
            "country_code": sender_country_code,
            "city": sender_city,
            "address": sender_address,
        }

        # ---------- to_location / delivery_point ----------
        delivery_point: str | None = None
        if delivery_mode == "office":
            # ПВЗ / постамат – структура как в твоём примере
            to_location: dict[str, Any] = {
                "code": addr["city_code"],
                "postal_code": addr["postal_code"],
                "country_code": addr.get("country_code", "RU"),
                "city": addr["city"],
                "address": addr["address"],
            }
            delivery_point = addr["code"]
        else:
            # доставка до двери – структура от Яндекса
            city = addr.get("city")
            postal_code = addr.get("postal_code")
            country_code = addr.get("country_code", "RU")
            formatted = addr.get("formatted") or addr.get("address")

            if not city or not postal_code:
                raise HTTPException(
                    status_code=400,
                    detail="CDEK door services: city or postal_code missing",
                )

            to_location = {
                "city": city,
                "postal_code": postal_code,
                "country_code": country_code,
                "address": formatted,
            }

        order_items: list[dict[str, Any]] = []
        for idx, it in enumerate(items, start=1):
            qty = int(it.get("qty", 1))
            item_id = it.get("id") or str(idx)
            feature_id = it.get("featureId")
            name = it.get("name")

            order_items.append(
                {
                    "name": name,
                    "ware_key": it.get("code", item_id),
                    "payment": {"value": 0},         # всё уже оплачено
                    "cost": 1,
                    "weight": 179,
                    "amount": qty,
                    "comment": str(feature_id or ""),
                }
            )

        package: dict[str, Any] = {
            "number": "1",
            "weight": 357,
            "length": 18,
            "width": 7,
            "height": 24,
            "items": order_items,
        }

        order_body: dict[str, Any] = {
            "type": 1,                                     # заказ интернет-магазина
            "number": order_number,
            "tariff_code": tariff["tariff_code"],          # 136 и т.п.
            "comment": f"Заказ из {source}",
            "recipient": recipient,
            "sender": sender,
            "from_location": from_location,
            "to_location": to_location,
            "packages": [package],
        }
        if delivery_point:
            order_body["delivery_point"] = delivery_point
            del order_body["to_location"]

        order_body.update({"delivery_recipient_cost": {"value": delivery_sum}})
        return order_body

    async def create_order_from_payload(self, payload: dict[str, Any], order_number: str, delivery_sum: float | int | None = None) -> dict[str, Any]:
        """
        Хелпер: берёт твой payload, собирает body для /v2/orders и шлёт запрос.
        """
        order = self.build_order_from_payload(payload, order_number, delivery_sum=delivery_sum)
        return await self.create_order(order)


# Глобальный клиент, как ты и делал
client = CDEKClientV2(
    account=CDEK_ACCOUNT,
    secure_password=CDEK_SECURE_PASSWORD,
    base_url=CDEK_API_URL,
)