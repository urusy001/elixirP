from __future__ import annotations

import uuid
import httpx
from typing import Any
from fastapi import HTTPException

from config import YOOKASSA_API_URL, YOOKASSA_SECRET_KEY, YOOKASSA_SHOP_ID
from src.webapp.models.checkout import build_receipt


async def create_yookassa_payment(payload, enriched_cart, order_number, delivery_fee: float | None = 0) -> dict[str, Any]:
    receipt = build_receipt(enriched_cart, delivery_fee)
    receipt["customer"] = {
        "full_name": f"{payload.contact_info.name} {payload.contact_info.surname}",
        "phone": payload.contact_info.phone,
        "email": payload.contact_info.email
    }

    # Add settlements (optional but recommended)
    total_amount = round(enriched_cart.get("total", 0), 2) + delivery_fee
    receipt["settlements"] = [
        {
            "type": "cashless",
            "amount": {"value": f"{total_amount:.2f}", "currency": "RUB"}
        }
    ]
    payment_payload = {
        "amount": {"value": f"{total_amount:.2f}", "currency": "RUB"},
        "confirmation": {"type": "redirect", "return_url": "http://localhost:3000/checkout-success"},
        "capture": True,
        "description": f"Заказ #{order_number}",
        "receipt": receipt
    }

    async with httpx.AsyncClient(auth=(YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY)) as client:
        response = await client.post(
            YOOKASSA_API_URL,
            json=payment_payload,
            headers={"Idempotence-Key": str(uuid.uuid4())},
        )

        if response.status_code not in (200, 201):
            raise HTTPException(status_code=500, detail=f"YooKassa error: {response.text}")

        data = response.json()
        return {
            "confirmation_url": data["confirmation"]["confirmation_url"],
            "order_id": order_number
        }
