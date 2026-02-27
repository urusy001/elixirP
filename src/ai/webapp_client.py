from __future__ import annotations

import hashlib
import hmac
import time
import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from types import SimpleNamespace
from typing import Any

import httpx

from config import API_PREFIX, NEW_BOT_TOKEN, WEBAPP_BASE_DOMAIN


class WebappBotApiError(RuntimeError):
    pass


def _base_url() -> str:
    if WEBAPP_BASE_DOMAIN: return WEBAPP_BASE_DOMAIN.rstrip("/")
    return "http://127.0.0.1:8000"


def _token_hash() -> str:
    if not NEW_BOT_TOKEN: raise WebappBotApiError("NEW_BOT_TOKEN is not configured")
    return hashlib.sha256(NEW_BOT_TOKEN.encode("utf-8")).hexdigest()


def _auth_headers() -> dict[str, str]:
    timestamp = str(int(time.time()))
    nonce = uuid.uuid4().hex
    token_hash = _token_hash()
    payload = f"{timestamp}:{nonce}:{token_hash}"
    signature = hmac.new(NEW_BOT_TOKEN.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return {"X-Bot-Timestamp": timestamp, "X-Bot-Nonce": nonce, "X-Bot-Token-Hash": token_hash, "X-Bot-Signature": signature}


def _to_jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"): return _to_jsonable(value.model_dump(exclude_unset=True))
    if hasattr(value, "dict"): return _to_jsonable(value.dict(exclude_unset=True))
    if isinstance(value, Decimal): return float(value)
    if isinstance(value, (datetime, date)): return value.isoformat()
    if isinstance(value, Enum): return value.value
    if isinstance(value, dict): return {k: _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, tuple): return [_to_jsonable(v) for v in value]
    if isinstance(value, list): return [_to_jsonable(v) for v in value]
    return value


def _to_obj(value: Any) -> Any:
    if isinstance(value, dict): return SimpleNamespace(**{k: _to_obj(v) for k, v in value.items()})
    if isinstance(value, list): return [_to_obj(v) for v in value]
    return value


class WebappBotClient:
    def __init__(self, timeout_seconds: float = 30.0):
        self.url = f"{_base_url()}{API_PREFIX}/internal/bot/rpc"
        self.timeout_seconds = timeout_seconds

    async def _rpc(self, action: str, payload: dict[str, Any] | None = None) -> Any:
        body = {"action": action, "payload": _to_jsonable(payload or {})}
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            resp = await client.post(self.url, json=body, headers=_auth_headers())
        if resp.status_code >= 400:
            try: detail = resp.json().get("detail")
            except Exception: detail = resp.text
            raise WebappBotApiError(f"Bot API error ({resp.status_code}) for action '{action}': {detail}")
        data = resp.json()
        if not data.get("ok"): raise WebappBotApiError(f"Bot API action '{action}' failed without ok=true")
        return data.get("result")

    async def get_user(self, column_name: str, raw_value: Any):
        return _to_obj(await self._rpc("get_user", {"column_name": column_name, "raw_value": raw_value}))

    async def get_users(self):
        return _to_obj(await self._rpc("get_users"))

    async def upsert_user(self, data: Any):
        return _to_obj(await self._rpc("upsert_user", {"data": data}))

    async def update_user(self, tg_id: int, data: Any):
        return _to_obj(await self._rpc("update_user", {"tg_id": tg_id, "data": data}))

    async def update_user_name(self, tg_id: int, first_name: str | None = None, last_name: str | None = None):
        return await self._rpc("update_user_name", {"tg_id": tg_id, "first_name": first_name, "last_name": last_name})

    async def increment_tokens(self, tg_id: int, input_inc: int = 0, output_inc: int = 0):
        return await self._rpc("increment_tokens", {"tg_id": tg_id, "input_inc": input_inc, "output_inc": output_inc})

    async def write_usage(self, user_id: int, input_tokens: int, output_tokens: int, bot: str, usage_date: date | None = None):
        return await self._rpc("write_usage", {"user_id": user_id, "input_tokens": input_tokens, "output_tokens": output_tokens, "bot": bot, "usage_date": usage_date})

    async def get_user_total_requests(self, user_id: int, bots: list[str] | tuple[str, ...] | None = None) -> int:
        return int(await self._rpc("get_user_total_requests", {"user_id": user_id, "bots": list(bots) if bots else None}))

    async def get_usages(self, start_date: date, end_date: date | None = None, bot: str | None = None) -> tuple[str, list[dict[str, Any]]]:
        result = await self._rpc("get_usages", {"start_date": start_date, "end_date": end_date, "bot": bot})
        return result["period_label"], result["usages"]

    async def get_user_usage_totals(self, user_id: int, start_date: date | None = None, end_date: date | None = None) -> dict[str, Any]:
        return await self._rpc("get_user_usage_totals", {"user_id": user_id, "start_date": start_date, "end_date": end_date})

    async def get_product_with_features(self, onec_id: str):
        return _to_obj(await self._rpc("get_product_with_features", {"onec_id": onec_id}))

    async def get_used_code_by_code(self, code: str):
        return _to_obj(await self._rpc("get_used_code_by_code", {"code": code}))

    async def create_used_code(self, data: Any):
        return _to_obj(await self._rpc("create_used_code", {"data": data}))

    async def list_promos(self):
        return _to_obj(await self._rpc("list_promos"))

    async def get_carts(self, exclude_starting: bool = True):
        return _to_obj(await self._rpc("get_carts", {"exclude_starting": exclude_starting}))

    async def get_user_carts(self, user_id: int, is_active: bool | None = None, exclude_starting: bool = True):
        return _to_obj(await self._rpc("get_user_carts", {"user_id": user_id, "is_active": is_active, "exclude_starting": exclude_starting}))

    async def get_carts_by_date(self, dt: datetime):
        return _to_obj(await self._rpc("get_carts_by_date", {"dt": dt}))

    async def get_cart_by_id(self, cart_id: int):
        return _to_obj(await self._rpc("get_cart_by_id", {"cart_id": cart_id}))

    async def search_users(self, by: str, value: Any, page: int | None = None, limit: int | None = None):
        result = await self._rpc("search_users", {"by": by, "value": value, "page": page, "limit": limit})
        return _to_obj(result["rows"]), int(result["total"])

    async def search_carts(self, value: Any, page: int | None = None, limit: int | None = None):
        result = await self._rpc("search_carts", {"value": value, "page": page, "limit": limit})
        return _to_obj(result["rows"]), int(result["total"])

    async def user_carts_analytics_text(self, user_id: int, days: int = 30, top_n: int = 5, recent_n: int = 8) -> str:
        return str(await self._rpc("user_carts_analytics_text", {"user_id": user_id, "days": days, "top_n": top_n, "recent_n": recent_n}))

    async def cart_analysis_text(self, cart_id: int) -> str:
        return str(await self._rpc("cart_analysis_text", {"cart_id": cart_id}))


webapp_client = WebappBotClient()
