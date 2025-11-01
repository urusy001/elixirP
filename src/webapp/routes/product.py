from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from config import templates
from src.webapp.crud import get_product_with_features
from src.webapp.database import get_db

router = APIRouter(prefix="/product")


@router.get("/{onec_id}/json", response_class=JSONResponse)
async def product_json(onec_id: str, db: AsyncSession = Depends(get_db)):
    product = await get_product_with_features(db, onec_id)
    if not product:
        return {"error": "Product not found"}

    features_list = [
        {
            "onec_id": f.onec_id,
            "name": f.name,
            "price": f.price,
            "balance": f.balance
        } for f in product.features
    ]

    return {
        "product": {
            "onec_id": product.onec_id,
            "name": product.name,
            "description": product.description
        },
        "features": features_list
    }


@router.get("{path:path}", response_class=HTMLResponse)
async def spa_product(request: Request, path: str):
    # Always return the SPA template
    return templates.TemplateResponse("index.html", {"request": request})
