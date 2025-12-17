import json
import logging
from decimal import Decimal

import httpx
from fastapi import Depends, HTTPException, APIRouter
from sqlalchemy.ext.asyncio import AsyncSession

from config import YANDEX_DELIVERY_TOKEN, YANDEX_WAREHOUSE_ADDRESS_FULLNAME, YANDEX_WAREHOUSE_LAT, YANDEX_WAREHOUSE_LON, \
    YANDEX_DELIVERY_BASE_URL
from src.delivery.sdek import client as cdek_client
from src.helpers import format_order_for_amocrm, normalize_address_for_cf
from src.webapp.crud import upsert_user, add_or_increment_item, create_cart, update_cart
from src.webapp.database import get_db
from src.webapp.models.checkout import CheckoutData
from src.webapp.routes.cart import cart_json
from src.webapp.schemas import UserCreate, CartCreate, CartItemCreate, CartUpdate

router = APIRouter(prefix="/payments", tags=["payments"])
log = logging.getLogger(__name__)


@router.post("/create", response_model=None)
async def create_payment(payload: CheckoutData, db: AsyncSession = Depends(get_db)):
    result = {}
    enriched_cart = await cart_json(payload.checkout_data, db=db)
    print(payload.model_dump_json(indent=4, ensure_ascii=False))
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
    address_str = normalize_address_for_cf(delivery_data["address"])
    payload_dict = payload.model_dump()
    cart_create = CartCreate(is_active=True, user_id=user_id, sum=total, delivery_sum=0, commentary=commentary_text, delivery_string=f"{delivery_service.upper()}: {address_str}")
    cart = await create_cart(db, cart_create)
    for item in enriched_cart.get("items", []):
        cart_item_create = CartItemCreate(product_onec_id=item["id"], feature_onec_id=item["featureId"], quantity=item["qty"])
        cart_item = await add_or_increment_item(db, cart.id, cart_item_create)

    user_upsert = UserCreate(**contact_info.model_dump(), tg_id=user_id)
    await upsert_user(db, user_upsert)

    log.info("Create payment payload: %s", ())
    order_number = cart.id
    if delivery_service == "yandex":
        offers_url = f"{YANDEX_DELIVERY_BASE_URL}/b2b/cargo/integration/v2/offers/calculate"
        claims_url = f"{YANDEX_DELIVERY_BASE_URL}/b2b/cargo/integration/v2/claims/create"

        headers = {
            "Authorization": f"Bearer {YANDEX_DELIVERY_TOKEN}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Accept-Language": "ru",
        }

        addr = delivery_data["address"]
        dest_fullname = addr.get("address") or addr.get("fullname") or address_str
        dest_lon, dest_lat = float(addr["coords"][0]), float(addr["coords"][1])
        wh_fullname = YANDEX_WAREHOUSE_ADDRESS_FULLNAME
        wh_lon = float(YANDEX_WAREHOUSE_LON)
        wh_lat = float(YANDEX_WAREHOUSE_LAT)

        dx_cm, dy_cm, dz_cm = 25, 15, 10
        weight_g = 100

        dx_m = float(Decimal(dx_cm) / Decimal("100"))
        dy_m = float(Decimal(dy_cm) / Decimal("100"))
        dz_m = float(Decimal(dz_cm) / Decimal("100"))
        weight_kg = float(Decimal(weight_g) / Decimal("1000"))

        offers_body = {
            "items": [{
                "quantity": 1,
                "pickup_point": 1,
                "dropoff_point": 2,
                "size": {"length": dx_m, "width": dy_m, "height": dz_m},
                "weight": weight_kg,
            }],
            "route_points": [
                {"id": 1, "coordinates": [wh_lon, wh_lat], "fullname": wh_fullname},
                {"id": 2, "coordinates": [dest_lon, dest_lat], "fullname": dest_fullname},
            ],
            "requirements": {
                "taxi_classes": ["express"],
                "pro_courier": False,
                "skip_door_to_door": False,
            },
        }

        async with httpx.AsyncClient(timeout=20.0) as client:
            offers_resp = await client.post(offers_url, json=offers_body, headers=headers)
            try:
                offers_resp.raise_for_status()
            except httpx.HTTPError:
                log.exception("Yandex offers/calculate error: %s", offers_resp.text)
                raise HTTPException(status_code=502, detail="Yandex Delivery offers/calculate error")

            offers_data = offers_resp.json()
            offers = offers_data.get("offers") or []
            if not offers:
                log.exception("Yandex: no offers returned: %s", offers_data)
                raise HTTPException(status_code=502, detail="Yandex Delivery: no delivery offers returned")

            chosen_offer = min(
                offers,
                key=lambda o: Decimal(
                    str(
                        (o.get("price") or {}).get("total_price_with_vat")
                        or (o.get("price") or {}).get("total_price")
                        or "999999999"
                    )
                ),
            )

            offer_payload = chosen_offer["payload"]
            price_obj = chosen_offer.get("price") or {}
            delivery_price = price_obj.get("total_price_with_vat") or price_obj.get("total_price")

            if delivery_price is not None:
                await update_cart(db, cart.id, CartUpdate(delivery_sum=float(Decimal(str(delivery_price)))))

            request_id = f"order-{order_number}"

            claim_body = {
                "items": [{
                    "extra_id": str(order_number),
                    "pickup_point": 1,
                    "dropoff_point": 2,
                    "title": f"Order #{order_number}",
                    "size": {"length": dx_m, "width": dy_m, "height": dz_m},
                    "weight": weight_kg,
                    "cost_value": str(total),
                    "cost_currency": "RUB",
                    "quantity": 1,
                }],
                "route_points": [
                    {
                        "point_id": 1,
                        "visit_order": 1,
                        "type": "source",
                        "contact": {
                            "name": "Elixir Peptide",
                            "phone": "+79610387977",
                            "email": "elixirpeptide@yandex.ru",
                        },
                        "address": {"fullname": wh_fullname, "coordinates": [wh_lon, wh_lat]},
                        "external_order_id": str(order_number),
                    },
                    {
                        "point_id": 2,
                        "visit_order": 2,
                        "type": "destination",
                        "contact": {
                            "name": f"{contact_info.name} {contact_info.surname}".strip(),
                            "phone": contact_info.phone,
                            "email": contact_info.email,
                        },
                        "address": {"fullname": dest_fullname, "coordinates": [dest_lon, dest_lat]},
                        "external_order_id": str(order_number),
                    },
                ],
                "comment": f"{commentary_text} | promo: {promocode}",
                "offer_payload": offer_payload,
            }

            claim_resp = await client.post(
                claims_url,
                params={"request_id": request_id},
                json=claim_body,
                headers=headers,
            )
            try:
                claim_resp.raise_for_status()
            except httpx.HTTPError:
                log.exception("Yandex claims/create error: %s", claim_resp.text)
                raise HTTPException(status_code=502, detail="Yandex Delivery claims/create error")

            claim_data = claim_resp.json()
            # Optional: store claim_data.get("id") / status in DB if you want tracking

        delivery_status = "ok"

    elif delivery_service == "cdek":
        delivery_sum = payload.selected_delivery["tariff"]["delivery_sum"]
        await update_cart(db, cart.id, CartUpdate(delivery_sum=delivery_sum))
        try: await cdek_client.create_order_from_payload(payload_dict, order_number, delivery_sum=delivery_sum)
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
            "address_str": address_str,
            "delivery_service": delivery_service,
            "price": total,
            "order_number": order_number,
            "note_text": format_order_for_amocrm(order_number, payload_dict, delivery_service, tariff, commentary_text, promocode),
            "payment_method": payment_method.upper(),
        }

        result["payment_method"] = payment_method
        from src.amocrm.client import amocrm
        lead = await amocrm.create_lead_with_contact_and_note(**order_lead_kwargs)

        if lead: return {
            "status": "success",
            "status_code": 202,
            "order_number": order_number,
        }

    raise HTTPException(status_code=400, detail="Failed when lead")
