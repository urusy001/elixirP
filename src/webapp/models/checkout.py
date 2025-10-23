from decimal import Decimal
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import Any, Dict, Optional
from pydantic import BaseModel, EmailStr, Field

async def enrich_cart_items(items: List[Dict], db: AsyncSession) -> Dict:
    from src.webapp.models import Feature
    """
    Given a list of items with 'featureId' and 'qty', returns enriched info:
    id, featureId, name, price, qty, subtotal
    """
    if not items:
        return {"items": [], "total": 0}

    feature_ids = [item["featureId"] for item in items if item.get("featureId")]
    feature_map = {}

    if feature_ids:
        result = await db.execute(select(Feature).where(Feature.onec_id.in_(feature_ids)))
        features = result.scalars().all()
        feature_map = {f.onec_id: f for f in features}

    enriched = []
    total = Decimal(0)

    for item in items:
        pid = item.get("id")
        fid = item.get("featureId")
        qty = item.get("qty", 1)

        feature = feature_map.get(fid)
        if feature:
            price = Decimal(feature.price)
            subtotal = price * qty
            total += subtotal

            enriched.append({
                "id": pid,
                "featureId": fid,
                "name": feature.name,       # ✅ feature name included
                "price": float(price),
                "qty": qty,
                "subtotal": float(subtotal)
            })

    return {
        "items": enriched,
        "total": float(total)
    }

def build_receipt(enriched_cart: dict, delivery_sum: Decimal = Decimal("0.00")):
    """
    Builds a fully valid YooKassa receipt from enriched cart data.
    """
    items = enriched_cart.get("items", [])
    receipt_items = []

    for item in items:
        price = Decimal(str(item.get("price", 0)))
        qty = Decimal(str(item.get("qty", 1)))

        receipt_items.append({
            "description": str(item.get("name") or item.get("id") or "Товар"),
            "quantity": f"{qty:.3f}",
            "amount": {
                "value": f"{price:.2f}",
                "currency": "RUB"
            },
            "vat_code": 2,
            # ✅ Required for fiscalization
            "payment_mode": "full_prepayment",
            "payment_subject": "commodity"
        })

    if delivery_sum and delivery_sum > 0:
        receipt_items.append({
            "description": "Доставка",
            "quantity": "1.000",
            "amount": {
                "value": f"{delivery_sum:.2f}",
                "currency": "RUB"
            },
            "vat_code": 2,
            "payment_mode": "full_prepayment",
            "payment_subject": "service"
        })

    # ✅ Include tax system code (1 = ОСН, adjust per your organization)
    return {
        "items": receipt_items,
        "tax_system_code": 1
    }

class ContactInfo(BaseModel):
    name: str = Field(..., example="Paylak")
    surname: str = Field(..., example="Urusyan")
    phone: str = Field(..., example="+17632730385")
    email: EmailStr = Field(..., example="urusy001@umn.edu")

class CheckoutData(BaseModel):
    checkout_data: Dict[str, Any]
    selected_delivery: Dict[str, Any]
    selected_delivery_service: str
    contact_info: Optional[ContactInfo] = None  # <-- added field