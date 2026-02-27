import hashlib
import hmac
import time

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from config import NEW_BOT_TOKEN
from src.helpers import cart_analysis_text, user_carts_analytics_text
from src.webapp.crud import (
    create_used_code,
    get_cart_by_id,
    get_carts,
    get_carts_by_date,
    get_product_with_features,
    get_used_code_by_code,
    get_usages,
    get_user,
    get_user_carts,
    get_user_total_requests,
    get_user_usage_totals,
    get_users,
    increment_tokens,
    list_promos,
    update_user,
    update_user_name,
    upsert_user,
    write_usage,
)
from src.webapp.crud.search import search_carts, search_users
from src.webapp.database import get_db
from src.webapp.schemas import UsedCodeCreate, UserCreate, UserUpdate

BOT_AUTH_MAX_SKEW_SECONDS = 300
router = APIRouter(prefix="/internal/bot", tags=["internal-bot"])


class BotRpcIn(BaseModel):
    action: str = Field(..., min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, Decimal): return float(value)
    if isinstance(value, (datetime, date)): return value.isoformat()
    if isinstance(value, Enum): return value.value
    if isinstance(value, list): return [_to_jsonable(v) for v in value]
    if isinstance(value, tuple): return [_to_jsonable(v) for v in value]
    if isinstance(value, dict): return {k: _to_jsonable(v) for k, v in value.items()}
    return value


def _serialize_user(user: Any) -> dict[str, Any] | None:
    if not user: return None
    return _to_jsonable(
        {
            "tg_id": user.tg_id,
            "tg_ref_id": user.tg_ref_id,
            "tg_phone": user.tg_phone,
            "photo_url": user.photo_url,
            "name": user.name,
            "surname": user.surname,
            "full_name": user.full_name,
            "email": user.email,
            "phone": user.phone,
            "premium_requests": user.premium_requests,
            "premium_until": user.premium_until,
            "thread_id": user.thread_id,
            "input_tokens": user.input_tokens,
            "output_tokens": user.output_tokens,
            "blocked_until": user.blocked_until,
            "contact_info": user.contact_info,
        }
    )


def _serialize_feature(feature: Any) -> dict[str, Any]:
    return _to_jsonable({"onec_id": feature.onec_id, "product_onec_id": feature.product_onec_id, "name": feature.name, "code": feature.code, "file_id": feature.file_id, "price": feature.price, "balance": feature.balance})


def _serialize_product(product: Any) -> dict[str, Any] | None:
    if not product: return None
    return _to_jsonable(
        {
            "id": product.id,
            "onec_id": product.onec_id,
            "name": product.name,
            "code": product.code,
            "description": product.description,
            "usage": product.usage,
            "expiration": product.expiration,
            "category_onec_id": product.category_onec_id,
            "features": [_serialize_feature(feature) for feature in (product.features or [])],
        }
    )


def _serialize_cart(cart: Any) -> dict[str, Any] | None:
    if not cart: return None
    user = getattr(cart, "user", None)
    return _to_jsonable(
        {
            "id": cart.id,
            "user_id": cart.user_id,
            "name": cart.name,
            "phone": cart.phone,
            "email": cart.email,
            "sum": cart.sum,
            "delivery_sum": cart.delivery_sum,
            "promo_code": cart.promo_code,
            "promo_gains": cart.promo_gains,
            "promo_gains_given": cart.promo_gains_given,
            "delivery_string": cart.delivery_string,
            "commentary": cart.commentary,
            "is_active": cart.is_active,
            "is_paid": cart.is_paid,
            "is_canceled": cart.is_canceled,
            "is_shipped": cart.is_shipped,
            "status": cart.status,
            "yandex_request_id": cart.yandex_request_id,
            "created_at": cart.created_at,
            "updated_at": cart.updated_at,
            "user": _serialize_user(user) if user else None,
        }
    )


def _serialize_promo(promo: Any) -> dict[str, Any] | None:
    if not promo: return None
    return _to_jsonable(
        {
            "id": promo.id,
            "code": promo.code,
            "discount_pct": promo.discount_pct,
            "owner_name": promo.owner_name,
            "owner_pct": promo.owner_pct,
            "owner_amount_gained": promo.owner_amount_gained,
            "lvl1_name": promo.lvl1_name,
            "lvl1_pct": promo.lvl1_pct,
            "lvl1_amount_gained": promo.lvl1_amount_gained,
            "lvl2_name": promo.lvl2_name,
            "lvl2_pct": promo.lvl2_pct,
            "lvl2_amount_gained": promo.lvl2_amount_gained,
            "times_used": promo.times_used,
            "created_at": promo.created_at,
            "updated_at": promo.updated_at,
        }
    )


def _serialize_used_code(code: Any) -> dict[str, Any] | None:
    if not code: return None
    return _to_jsonable({"id": code.id, "user_id": code.user_id, "code": code.code, "price": code.price})


def _parse_date(value: Any, field_name: str) -> date | None:
    if value is None: return None
    if isinstance(value, date) and not isinstance(value, datetime): return value
    try: return date.fromisoformat(str(value))
    except Exception as exc: raise HTTPException(status_code=422, detail=f"Invalid date for '{field_name}'") from exc


def _parse_datetime(value: Any, field_name: str) -> datetime:
    if isinstance(value, datetime): return value
    try: return datetime.fromisoformat(str(value))
    except Exception as exc: raise HTTPException(status_code=422, detail=f"Invalid datetime for '{field_name}'") from exc


def _expected_token_hash() -> str:
    if not NEW_BOT_TOKEN: raise HTTPException(status_code=500, detail="NEW_BOT_TOKEN is not configured")
    return hashlib.sha256(NEW_BOT_TOKEN.encode("utf-8")).hexdigest()


def _verify_bot_auth(request: Request) -> None:
    timestamp = request.headers.get("X-Bot-Timestamp")
    nonce = request.headers.get("X-Bot-Nonce")
    token_hash = request.headers.get("X-Bot-Token-Hash")
    signature = request.headers.get("X-Bot-Signature")
    if not timestamp or not nonce or not token_hash or not signature: raise HTTPException(status_code=401, detail="Missing bot auth headers")
    try: ts = int(timestamp)
    except Exception as exc: raise HTTPException(status_code=401, detail="Invalid bot timestamp") from exc
    if abs(int(time.time()) - ts) > BOT_AUTH_MAX_SKEW_SECONDS: raise HTTPException(status_code=401, detail="Expired bot auth timestamp")
    expected_hash = _expected_token_hash()
    if not hmac.compare_digest(token_hash, expected_hash): raise HTTPException(status_code=401, detail="Invalid bot token hash")
    payload = f"{timestamp}:{nonce}:{token_hash}"
    expected_sig = hmac.new(NEW_BOT_TOKEN.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected_sig): raise HTTPException(status_code=401, detail="Invalid bot signature")


@router.post("/rpc")
async def bot_rpc(body: BotRpcIn, db: AsyncSession = Depends(get_db), _: None = Depends(_verify_bot_auth)):
    action = body.action
    payload = body.payload
    if action == "get_user":
        user = await get_user(db, payload.get("column_name"), payload.get("raw_value"))
        return {"ok": True, "result": _serialize_user(user)}

    if action == "get_users":
        users = await get_users(db)
        return {"ok": True, "result": [_serialize_user(user) for user in users]}

    if action == "upsert_user":
        user = await upsert_user(db, UserCreate(**(payload.get("data") or {})))
        return {"ok": True, "result": _serialize_user(user)}

    if action == "update_user":
        user = await update_user(db, int(payload["tg_id"]), UserUpdate(**(payload.get("data") or {})))
        return {"ok": True, "result": _serialize_user(user)}

    if action == "update_user_name":
        await update_user_name(int(payload["tg_id"]), payload.get("first_name"), payload.get("last_name"))
        return {"ok": True, "result": True}

    if action == "increment_tokens":
        await increment_tokens(db, int(payload["tg_id"]), int(payload.get("input_inc") or 0), int(payload.get("output_inc") or 0))
        return {"ok": True, "result": True}

    if action == "write_usage":
        usage_date = _parse_date(payload.get("usage_date"), "usage_date")
        usage = await write_usage(db, int(payload["user_id"]), int(payload["input_tokens"]), int(payload["output_tokens"]), payload["bot"], usage_date=usage_date)
        return {"ok": True, "result": _to_jsonable({"id": usage.id})}

    if action == "get_user_total_requests":
        total = await get_user_total_requests(db, int(payload["user_id"]), payload.get("bots"))
        return {"ok": True, "result": total}

    if action == "get_usages":
        start_date = _parse_date(payload.get("start_date"), "start_date")
        if not start_date: raise HTTPException(status_code=422, detail="start_date is required")
        end_date = _parse_date(payload.get("end_date"), "end_date")
        period_label, usages = await get_usages(db, start_date=start_date, end_date=end_date, bot=payload.get("bot"))
        return {"ok": True, "result": _to_jsonable({"period_label": period_label, "usages": usages})}

    if action == "get_user_usage_totals":
        start_date = _parse_date(payload.get("start_date"), "start_date")
        end_date = _parse_date(payload.get("end_date"), "end_date")
        totals = await get_user_usage_totals(db, int(payload["user_id"]), start_date=start_date, end_date=end_date)
        return {"ok": True, "result": _to_jsonable(totals)}

    if action == "get_product_with_features":
        product = await get_product_with_features(db, payload.get("onec_id"))
        return {"ok": True, "result": _serialize_product(product)}

    if action == "get_used_code_by_code":
        used_code = await get_used_code_by_code(db, str(payload.get("code") or ""))
        return {"ok": True, "result": _serialize_used_code(used_code)}

    if action == "create_used_code":
        used_code = await create_used_code(db, UsedCodeCreate(**(payload.get("data") or {})))
        return {"ok": True, "result": _serialize_used_code(used_code)}

    if action == "list_promos":
        promos = await list_promos(db)
        return {"ok": True, "result": [_serialize_promo(promo) for promo in promos]}

    if action == "get_carts":
        carts = await get_carts(db, exclude_starting=bool(payload.get("exclude_starting", True)))
        return {"ok": True, "result": [_serialize_cart(cart) for cart in (carts or [])]}

    if action == "get_user_carts":
        carts = await get_user_carts(db, int(payload["user_id"]), is_active=payload.get("is_active"), exclude_starting=bool(payload.get("exclude_starting", True)))
        return {"ok": True, "result": [_serialize_cart(cart) for cart in carts]}

    if action == "get_carts_by_date":
        dt = _parse_datetime(payload.get("dt"), "dt")
        carts = await get_carts_by_date(db, dt=dt)
        return {"ok": True, "result": [_serialize_cart(cart) for cart in carts]}

    if action == "get_cart_by_id":
        cart = await get_cart_by_id(db, int(payload["cart_id"]))
        return {"ok": True, "result": _serialize_cart(cart)}

    if action == "search_users":
        rows, total = await search_users(db, payload.get("by"), payload.get("value"), page=payload.get("page"), limit=payload.get("limit"))
        return {"ok": True, "result": {"rows": [_serialize_user(row) for row in rows], "total": total}}

    if action == "search_carts":
        rows, total = await search_carts(db, payload.get("value"), page=payload.get("page"), limit=payload.get("limit"))
        return {"ok": True, "result": {"rows": [_serialize_cart(row) for row in rows], "total": total}}

    if action == "user_carts_analytics_text":
        text = await user_carts_analytics_text(db, int(payload["user_id"]), days=int(payload.get("days", 30)), top_n=int(payload.get("top_n", 5)), recent_n=int(payload.get("recent_n", 8)))
        return {"ok": True, "result": text}

    if action == "cart_analysis_text":
        text = await cart_analysis_text(db, int(payload["cart_id"]))
        return {"ok": True, "result": text}

    raise HTTPException(status_code=400, detail=f"Unknown bot action: {action}")
