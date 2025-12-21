import json
import logging
from decimal import Decimal, ROUND_HALF_UP

import httpx
from fastapi import Depends, HTTPException, APIRouter
from sqlalchemy.ext.asyncio import AsyncSession

from config import YANDEX_DELIVERY_TOKEN, YANDEX_DELIVERY_BASE_URL, YANDEX_DELIVERY_WAREHOUSE_ID
from src.services.cdek import client as cdek_client
from src.helpers import format_order_for_amocrm, normalize_address_for_cf
from src.webapp.crud import upsert_user, add_or_increment_item, create_cart, update_cart, get_promo_by_code, \
    update_promo
from src.webapp.database import get_db
from src.webapp.models.checkout import CheckoutData
from src.webapp.routes.cart import cart_json
from src.webapp.routes.promocodes import Q2, D100
from src.webapp.schemas import UserCreate, CartCreate, CartItemCreate, CartUpdate, PromoCodeUpdate

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
    print(payload.promocode)
    promocode = payload.promocode.code or "Не указан"
    if promocode:
        promo_code = await get_promo_by_code(db, promocode.strip())
        if not promo_code: raise HTTPException(status_code=404, detail="Promo code not found")
        if total <= 0: raise HTTPException(status_code=400, detail="Price must be greater than 0")

        discount_pct = Decimal(promo_code.discount_pct or 0)
        owner_pct = Decimal(promo_code.owner_pct or 0)
        lvl1_pct = Decimal(promo_code.lvl1_pct or 0)
        lvl2_pct = Decimal(promo_code.lvl2_pct or 0)

        total = (total * (D100 - discount_pct) / D100).quantize(Q2, rounding=ROUND_HALF_UP)

        new_owner_gained = (Decimal(promo_code.owner_amount_gained or 0) + (total * owner_pct / D100)).quantize(Q2, rounding=ROUND_HALF_UP)
        new_lvl1_gained  = (Decimal(promo_code.lvl1_amount_gained  or 0) + (total * lvl1_pct  / D100)).quantize(Q2, rounding=ROUND_HALF_UP)
        new_lvl2_gained  = (Decimal(promo_code.lvl2_amount_gained  or 0) + (total * lvl2_pct  / D100)).quantize(Q2, rounding=ROUND_HALF_UP)

        promo_code_update = PromoCodeUpdate(
            owner_amount_gained=new_owner_gained,
            lvl1_amount_gained=new_lvl1_gained,
            lvl2_amount_gained=new_lvl2_gained,
            times_used=(promo_code.times_used or 0) + 1,
        )

        await update_promo(db, promo_code.id, promo_code_update)
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
        delivery_sum = payload.selected_delivery["delivery_sum"]
        request_create_url = f"{YANDEX_DELIVERY_BASE_URL}/api/b2b/platform/request/create"

        headers = {
            "Authorization": f"Bearer {YANDEX_DELIVERY_TOKEN}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Accept-Language": "ru",
        }

        dx_cm, dy_cm, dz_cm = 25, 15, 10
        weight_g = 100

        total_kop = int(Decimal(str(total)) * 100)
        request_id_param = f"order-{order_number}"
        pvz_platform_id = delivery_data["address"].get("code", None)

        if pvz_platform_id:
            destination_node = {
                "type": "platform_station",
                "platform_station": {"platform_id": str(pvz_platform_id)},
            }
            last_mile_policy = "self_pickup"
        else:
            destination_node = {
                "type": "custom_location",
                "custom_location": {"details": {"full_address": address_str}},
            }
            last_mile_policy = "time_interval"

        request_body = {
            "info": {
                "operator_request_id": str(order_number),
                "comment": f"{commentary_text} | promo: {promocode}",
            },
            "source": {
                "platform_station": {"platform_id": str(YANDEX_DELIVERY_WAREHOUSE_ID)},
            },
            "destination": destination_node,
            "items": [
                {
                    "count": 1,
                    "name": f"Order #{order_number}",
                    "article": f"ORDER-{order_number}",
                    "billing_details": {
                        "unit_price": total_kop,
                        "assessed_unit_price": total_kop,
                        "nds": -1,
                    },
                    "physical_dims": {"dx": dx_cm, "dy": dy_cm, "dz": dz_cm},
                    "place_barcode": "box-1",
                }
            ],
            "places": [
                {
                    "barcode": "box-1",
                    "description": f"Box for order #{order_number}",
                    "physical_dims": {
                        "dx": dx_cm,
                        "dy": dy_cm,
                        "dz": dz_cm,
                        "weight_gross": weight_g,
                    },
                }
            ],
            "billing_info": {
                "payment_method": "already_paid" if payment_method.lower() in ("paid", "already_paid") else "already_paid",
            },
            "recipient_info": {
                "first_name": (contact_info.name or "Получатель"),
                "last_name": (contact_info.surname or ""),
                "phone": contact_info.phone,
                "email": contact_info.email,
            },
            "last_mile_policy": last_mile_policy,
            "particular_items_refuse": False,
            "forbid_unboxing": False,
        }

        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                request_create_url,
                params={"send_unix": True},
                json=request_body,
                headers=headers,
            )
            try: resp.raise_for_status()
            except httpx.HTTPError:
                log.exception("Yandex NDD request/create error: %s", resp.text)
                raise HTTPException(status_code=502, detail="Yandex Delivery request/create error")

            yandex_data = resp.json()
            print(json.dumps(yandex_data, indent=4, ensure_ascii=False))

        yandex_request_id = yandex_data.get("request_id")
        if yandex_request_id: await update_cart(db, cart.id, CartUpdate(yandex_request_id=yandex_request_id))
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

    else: raise HTTPException(status_code=400, detail="Unsupported services service")
    if delivery_status == "ok":
        order_lead_kwargs = {
            "lead_name": f"{contact_info.name} {contact_info.surname}",
            "phone": contact_info.phone,
            "email": contact_info.email,
            "address_str": address_str,
            "delivery_service": delivery_service,
            "price": total,
            "order_number": order_number,
            "note_text": format_order_for_amocrm(order_number, payload_dict, delivery_service, tariff, commentary_text, promo_code.code or None, delivery_sum),
            "payment_method": payment_method.upper(),
            "delivery_sum": delivery_sum,
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
