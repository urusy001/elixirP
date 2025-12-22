import re
from decimal import Decimal, ROUND_HALF_UP
from urllib.parse import parse_qs

import aiosmtplib
from fastapi import APIRouter, Request, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import JSONResponse

from src.webapp.crud import update_cart, get_promo_by_code, update_promo
from src.webapp.database import get_db
from src.webapp.routes.promocodes import Q2, D100
from src.webapp.schemas import VerifyOrderIn, VerifyOrderOut, CartUpdate, PromoCodeUpdate

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

@router.get("/amocrm")
async def get_webhook(request: Request):
    try: print(await request.json())
    except: print(await request.body())


@router.post("/amocrm")
async def get_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    body = await request.body()
    q = parse_qs(body.decode("utf-8", "replace"), keep_blank_values=True)

    lead_id = int((q.get("leads[status][0][id]") or ["0"])[0] or "0")
    status_id = int((q.get("leads[status][0][status_id]") or ["0"])[0] or "0")
    pipeline_id = int((q.get("leads[status][0][pipeline_id]") or ["0"])[0] or "0")
    if not lead_id: return JSONResponse({"ok": True, "ignored": "no lead_id"})
    from src.amocrm.client import amocrm
    if pipeline_id and pipeline_id != amocrm.PIPELINE_ID: return JSONResponse({"ok": True, "ignored": "wrong pipeline"})

    try:
        lead = await amocrm.get(f"/api/v4/leads/{lead_id}")
        name = lead.get("name") or ""
        status_id = int(lead.get("status_id") or status_id or 0)
        pipeline_id = int(lead.get("pipeline_id") or pipeline_id or 0)
        if pipeline_id and pipeline_id != amocrm.PIPELINE_ID: return JSONResponse({"ok": True, "ignored": "pipeline mismatch"})
        m = re.search(r"№\s*(\d+)", name)
        if not m:
            amocrm.logger.warning("Lead %s name has no cart id: %r", lead_id, name)
            return JSONResponse({"ok": True, "ignored": "no cart id in lead name"})

        cart_id = int(m.group(1))
        status_text = amocrm.STATUS_WORDS.get(status_id, f"Статус {status_id}")
        is_active = bool(status_id not in amocrm.COMPLETE_STATUS_IDS)
        cart = await update_cart(db, cart_id, CartUpdate(status=status_text, is_active=is_active))
        if not cart.is_active and not cart.promo_gains_given:
            print(cart.to_dict())
            code = cart.promo_code
            promo_code = await get_promo_by_code(db, code)
            if promo_code:
                print(promo_code.code)
                owner_pct = Decimal(promo_code.owner_pct or 0)
                lvl1_pct = Decimal(promo_code.lvl1_pct or 0)
                lvl2_pct = Decimal(promo_code.lvl2_pct or 0)

                new_owner_gained = (Decimal(promo_code.owner_amount_gained or 0) + (cart.sum * owner_pct / D100)).quantize(Q2, rounding=ROUND_HALF_UP)
                new_lvl1_gained  = (Decimal(promo_code.lvl1_amount_gained  or 0) + (cart.sum * lvl1_pct  / D100)).quantize(Q2, rounding=ROUND_HALF_UP)
                new_lvl2_gained  = (Decimal(promo_code.lvl2_amount_gained  or 0) + (cart.sum * lvl2_pct  / D100)).quantize(Q2, rounding=ROUND_HALF_UP)
                promo_code = await update_promo(db, promo_code.id, PromoCodeUpdate(owner_amount_gained=new_owner_gained, lvl1_amount_gained=new_lvl1_gained, lvl2_amount_gained=new_lvl2_gained))
                amocrm.logger.info(f"Promo code {promo_code.code} gains updated:\n"
                                   f"{promo_code.owner_name} — {promo_code.owner_amount_gained}\n"
                                   f"{promo_code.lvl1_name} — {promo_code.lvl1_amount_gained}\n"
                                   f"{promo_code.lvl2_name} — {promo_code.lvl2_amount_gained}\n")

        amocrm.logger.info("Lead %s cart updated successfully", lead_id)
        return JSONResponse({"ok": True, "cart_id": cart_id, "lead_id": lead_id, "status_id": status_id})

    except Exception:
        amocrm.logger.exception("Webhook failed lead_id=%s", lead_id)
        return JSONResponse({"ok": True, "ignored": "exception"})


@router.put("/amocrm")
async def get_webhook(request: Request):
    try: print(await request.json())
    except: print(await request.body())


@router.delete("/amocrm")
async def get_webhook(request: Request):
    try: print(await request.json())
    except: print(await request.body())


@router.post("/verify-order", response_model=VerifyOrderOut)
async def verify_order(payload: VerifyOrderIn) -> VerifyOrderOut:
    code = payload.code
    from src.amocrm.client import amocrm
    try: price, email, verif_code = await amocrm.get_valid_deal_price_and_email_verification_code_for_ai(code)
    except (aiosmtplib.errors.SMTPException, OSError, TimeoutError) as e:
        return VerifyOrderOut(
            status="smtp_failed",
            price="not_found",  # или None, как тебе удобнее
            email=None,
            verification_code=None,
        )

    if price == "not_found": return VerifyOrderOut(status="not_found", price="not_found", email=None, verification_code=None)
    if not email or not verif_code: return VerifyOrderOut(status="no_email", price=price, email=email, verification_code=None)
    return VerifyOrderOut(status="ok", price=price, email=email, verification_code=verif_code)
