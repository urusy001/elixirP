from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query, Depends, Body
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.webapp.crud import get_product, get_feature
from src.webapp.database import get_db
from src.webapp.models import Feature

router = APIRouter(prefix="/cart", tags=["cart"])


@router.get("/product/{onec_id}")
async def get_cart_product(
        onec_id: str,
        feature_id: str = Query("", alias="feature_id"),
        db: AsyncSession = Depends(get_db)
):
    # Fetch product
    product = await get_product(db, 'onec_id', onec_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    feature = None
    print(onec_id, feature_id)
    if feature_id:
        feature = await get_feature(db, 'onec_id', feature_id)
        if not feature:
            raise HTTPException(status_code=404, detail="Feature not found")

    return {"product": product, "feature": feature}


@router.post("/json")
async def cart_json(cart_data: dict = Body(...), db: AsyncSession = Depends(get_db)):
    """
    Receives the current cart from frontend and returns
    enriched data (features, totals).
    """

    items = cart_data.get("items", [])
    if not items:
        return {"items": [], "total": 0}

    # Collect all featureIds in the cart
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
                "price": float(price),
                "qty": qty,
                "subtotal": float(subtotal)
            })

    return {
        "items": enriched,
        "total": float(total)
    }
