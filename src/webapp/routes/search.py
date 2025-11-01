from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.helpers import normalize
from src.webapp.database import get_db
from src.webapp.models import Product

router = APIRouter(prefix="/search", tags=["search"])


@router.get("/")
async def search(
        q: Optional[str] = Query(None),
        page: int = Query(0, ge=0),
        limit: int = Query(10, ge=1),
        db: AsyncSession = Depends(get_db),
):
    offset = page * limit
    filtered = []
    batch_size = 50  # fetch in small batches from DB
    skip = 0

    while len(filtered) < offset + limit:
        result = await db.execute(
            select(Product)
            .options(selectinload(Product.features))
            .offset(skip)
            .limit(batch_size)
        )
        batch = result.scalars().all()
        if not batch:
            break

        for product in batch:
            if not product.features:
                continue

            if q and await normalize(q) not in await normalize(product.name):
                continue

            filtered.append({
                "name": product.name,
                "url": f"/product/{product.onec_id}",
                "image": "/static/images/product.png",
                "features": [
                    {"id": f.onec_id, "name": f.name, "price": float(f.price)}
                    for f in product.features
                ]
            })

        skip += batch_size

    page_results = filtered[offset: offset + limit]

    total = len(filtered) if q else await db.scalar(select(func.count()).select_from(Product))
    return {"results": page_results, "total": total}
