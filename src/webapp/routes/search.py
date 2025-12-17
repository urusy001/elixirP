from typing import Optional, List, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.helpers import normalize
from src.webapp.database import get_db
from src.webapp.models import Product
from src.webapp.models.product_tg_categories import product_tg_categories  # <- IMPORTANT

router = APIRouter(prefix="/search", tags=["search"])


async def _filtered_product_onec_ids_by_tg_categories(
        db: AsyncSession,
        tg_category_ids: list[int],
        mode: Literal["any", "all"] = "any",
) -> set[str]:
    if not tg_category_ids:
        return set()

    if mode == "any":
        stmt = (
            select(product_tg_categories.c.product_onec_id)
            .where(product_tg_categories.c.tg_category_id.in_(tg_category_ids))
            .distinct()
        )
        rows = (await db.execute(stmt)).scalars().all()
        return set(rows)

    # mode == "all": product must have ALL selected categories
    stmt = (
        select(product_tg_categories.c.product_onec_id)
        .where(product_tg_categories.c.tg_category_id.in_(tg_category_ids))
        .group_by(product_tg_categories.c.product_onec_id)
        .having(func.count(func.distinct(product_tg_categories.c.tg_category_id)) == len(tg_category_ids))
    )
    rows = (await db.execute(stmt)).scalars().all()
    return set(rows)


async def search_products(
        db: AsyncSession,
        q: Optional[str],
        page: int,
        limit: int,
        tg_category_ids: Optional[list[int]] = None,
        tg_category_mode: Literal["any", "all"] = "any",
):
    offset = page * limit
    filtered = []
    batch_size = 50
    skip = 0

    norm_q = await normalize(q) if q else None

    allowed_onec_ids: Optional[set[str]] = None
    if tg_category_ids:
        allowed_onec_ids = await _filtered_product_onec_ids_by_tg_categories(
            db,
            tg_category_ids=tg_category_ids,
            mode=tg_category_mode,
        )

        # nothing matches => return empty fast
        if not allowed_onec_ids:
            return {"results": [], "total": 0}

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

            if allowed_onec_ids is not None and product.onec_id not in allowed_onec_ids:
                continue

            if norm_q and norm_q not in await normalize(product.name):
                continue

            filtered.append(
                {
                    "name": product.name,
                    "url": f"/product/{product.onec_id}",
                    "image": "/static/images/product.png",
                    "features": [
                        {"id": f.onec_id, "name": f.name, "price": float(f.price), "balance": f.balance}
                        for f in product.features
                    ],
                }
            )

        skip += batch_size

    page_results = filtered[offset: offset + limit]

    # IMPORTANT: total should reflect filters too
    total = len(filtered)

    return {"results": page_results, "total": total}


@router.get("")  # <- no trailing slash => no 307 redirect
async def search(
        q: Optional[str] = Query(None),
        page: int = Query(0, ge=0),
        limit: int = Query(10, ge=1),

        tg_category_ids: Optional[List[int]] = Query(None),  # supports ?tg_category_ids=1&tg_category_ids=2
        tg_category_mode: Literal["any", "all"] = Query("any"),

        db: AsyncSession = Depends(get_db),
):
    return await search_products(
        db,
        q=q,
        page=page,
        limit=limit,
        tg_category_ids=tg_category_ids,
        tg_category_mode=tg_category_mode,
    )