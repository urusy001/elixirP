import asyncio
import json
import logging
import httpx
from datetime import datetime
from fastapi import Depends, HTTPException, APIRouter
from sqlalchemy.ext.asyncio import AsyncSession

from config import (
    YANDEX_DELIVERY_BASE_URL,
    YANDEX_DELIVERY_TOKEN,
    YANDEX_DELIVERY_WAREHOUSE_ID
)
from src.delivery.sdek import client as cdek_client
from src.helpers import format_order_for_amocrm
from src.webapp.crud import upsert_user
from src.webapp.database import get_db
from src.webapp.models.checkout import CheckoutData
from src.webapp.routes.cart import cart_json
from src.webapp.schemas import UserCreate

router = APIRouter(prefix="/payments", tags=["payments"])
log = logging.getLogger(__name__)


@router.post("/create", response_model=None)
async def create_payment(payload: CheckoutData, db: AsyncSession = Depends(get_db)):
    result = {}
    enriched_cart = await cart_json(payload.checkout_data, db=db)
    print(json.dumps(enriched_cart, ensure_ascii=False, indent=4))
    delivery_service = payload.selected_delivery_service.lower()
    delivery_data = payload.selected_delivery
    tariff = delivery_data["deliveryMode"]
    contact_info = payload.contact_info
    user_id = payload.user_id
    checkout_data = payload.checkout_data
    total = checkout_data["total"]
    payment_method = payload.payment_method
    promocode = payload.promocode or "Не указан"
    commentary_text = payload.commentary or "Не указан"

    payload_dict = payload.model_dump()

    user_upsert = UserCreate(**contact_info.model_dump(), tg_id=user_id)
    await upsert_user(db, user_upsert)

    log.info("Create payment payload: %s", ())
    order_number = str(int(datetime.now().timestamp()))
    if delivery_service == "yandex":
        url = f"{YANDEX_DELIVERY_BASE_URL}/api/b2b/platform/pricing-calculator"
        addr = delivery_data["address"]
        if tariff == "time_interval": destination = {"address": addr["address"]}
        else: destination = {"platform_station_id": addr["code"]}

        body = {
            "source": {"platform_station_id": YANDEX_DELIVERY_WAREHOUSE_ID},
            "destination": destination,
            "tariff": tariff,
            "total_weight": 100,
            "payment_method": "already_paid",
            "client_price": 200000,
            "total_assessed_price": 200000,
            "places": [
                {"physical_dims": {"dx": 25, "dy": 15, "dz": 10, "weight_gross": 100}}
            ],
        }
        params = {"is_oversized": False}
        headers = {
            "Authorization": f"Bearer {YANDEX_DELIVERY_TOKEN}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, params=params, json=body, headers=headers)
            try: resp.raise_for_status()
            except httpx.HTTPError as e:
                log.exception("Yandex Delivery error: %s", resp.text)
                raise HTTPException(status_code=502, detail="Yandex Delivery API error")

        delivery_status = "ok"

    elif delivery_service == "cdek":
        try: await cdek_client.create_order_from_payload(payload_dict, order_number)
        except HTTPException: raise
        except Exception as e:
            log.exception("CDEK create_order failed: %s", e)
            raise HTTPException(status_code=502, detail="CDEK API error")

        delivery_status = "ok"

    else: raise HTTPException(status_code=400, detail="Unsupported delivery service")
    if delivery_status == "ok":
        order_lead_kwargs = {
            "lead_name": f"{contact_info.name} {contact_info.surname}",
            "phone": contact_info.phone,
            "email": contact_info.email,
            "address": delivery_data["address"],
            "delivery_service": delivery_service,
            "price": total,
            "order_number": order_number,
            "note_text": format_order_for_amocrm(order_number, payload_dict, delivery_service, tariff, commentary_text, promocode),
            "payment_method": payment_method.upper(),
        }

        result["payment_method"] = payment_method
        from src.amocrm.client import amocrm
        result = await amocrm.create_lead_with_contact_and_note(**order_lead_kwargs)
        return result

    raise HTTPException(status_code=400, detail="Failed when lead")
