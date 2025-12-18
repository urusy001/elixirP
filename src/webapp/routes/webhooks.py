import aiosmtplib
from fastapi import APIRouter, Request

from src.webapp.schemas import VerifyOrderIn, VerifyOrderOut

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

@router.get("/amocrm")
async def get_webhook(request: Request):
    try: print(await request.json())
    except: print(await request.body())



@router.post("/amocrm")
async def get_webhook(request: Request):
    try: print(await request.json())
    except: print(await request.body())


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
