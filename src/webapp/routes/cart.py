from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query, Depends, Body
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.webapp.crud import get_product, get_feature, create_cart, get_user_carts_webapp
from src.webapp.database import get_db
from src.webapp.models import Feature
from src.webapp.schemas import CartWebRead, CartCreate

router = APIRouter(prefix="/cart", tags=["cart"])

@router.get("/", response_model=list[CartWebRead])
async def get_orders(user_id: int = Query(...), db: AsyncSession = Depends(get_db)):
    carts = await get_user_carts_webapp(db, user_id)
    carts = [c for c in carts if 'ачальная' not in (c.name or "")]
    return carts

@router.get("/product/{onec_id}")
async def get_cart_product(onec_id: str, feature_id: str = Query("", alias="feature_id"), db: AsyncSession = Depends(get_db)):
    product = await get_product(db, 'onec_id', onec_id)
    if not product: raise HTTPException(status_code=404, detail="Product not found")

    feature = None
    if feature_id:
        feature = await get_feature(db, 'onec_id', feature_id)
        if not feature: raise HTTPException(status_code=404, detail="Feature not found")

    return {"product": product.to_dict(), "feature": feature.to_dict()}

@router.post("/create")
async def create(cart_data: CartCreate, db: AsyncSession = Depends(get_db)):
    cart = await create_cart(db, cart_data)
    return cart.to_dict()

@router.post("/json")
async def cart_json(cart_data: dict = Body(...), db: AsyncSession = Depends(get_db)):
    """
    Receives the current cart from frontend and returns
    enriched data (features, totals).
    """

    items = cart_data.get("items", [])
    if not items: return {"items": [], "total": 0}

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

        feature: Feature = feature_map.get(fid)
        if feature:
            price = Decimal(feature.price)
            subtotal = price * qty
            total += subtotal
            enriched.append({
                "id": pid,
                "name": f'{item.get("name")}',
                "featureId": fid,
                "price": float(price),
                "qty": qty,
                "subtotal": float(subtotal)
            })

    return {
        "items": enriched,
        "total": float(total)
    }
