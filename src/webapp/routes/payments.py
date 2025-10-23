import uuid
import httpx

from datetime import datetime
from decimal import Decimal
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from config import YOOKASSA_API_URL, YOOKASSA_SECRET_KEY, YOOKASSA_SHOP_ID
from src.webapp.database import get_db
from src.webapp.models.checkout import CheckoutData, build_receipt
from src.webapp.routes.cart import cart_json

router = APIRouter(prefix="/payments", tags=["payments"])

@router.post("/create", response_model=None)
async def create_payment(payload: CheckoutData, db: AsyncSession = Depends(get_db)):
    enriched_cart = await cart_json(payload.checkout_data, db=db)
    total_amount = Decimal(enriched_cart.get("total", 0))
    delivery_fee = Decimal(payload.selected_delivery.get("tariff", {}).get("delivery_sum", 0))
    receipt = build_receipt(enriched_cart, delivery_fee)

    # Attach customer data
    receipt["customer"] = {
        "full_name": f"{payload.contact_info.name} {payload.contact_info.surname}",
        "phone": payload.contact_info.phone,
        "email": payload.contact_info.email
    }

    # Add settlements (optional but recommended)
    total_amount = Decimal(enriched_cart.get("total", 0)) + delivery_fee
    receipt["settlements"] = [
        {
            "type": "cashless",
            "amount": {"value": f"{total_amount:.2f}", "currency": "RUB"}
        }
    ]
    order_id = f"{int(datetime.utcnow().timestamp())}"
    payment_payload = {
        "amount": {"value": f"{total_amount:.2f}", "currency": "RUB"},
        "confirmation": {"type": "redirect", "return_url": "http://localhost:3000/checkout-success"},
        "capture": True,
        "description": f"Заказ #{order_id}",
        "receipt": receipt
    }
    print(payment_payload)

    async with httpx.AsyncClient(auth=(YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY)) as client:
        response = await client.post(
            YOOKASSA_API_URL,
            json=payment_payload,
            headers={"Idempotence-Key": str(uuid.uuid4())},
        )

        if response.status_code not in (200, 201):
            print(response.json())
            raise HTTPException(status_code=500, detail=f"YooKassa error: {response.text}")

        data = response.json()
        print(data)
        return {
            "confirmation_url": data["confirmation"]["confirmation_url"],
            "order_id": order_id
        }

