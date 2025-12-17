from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, distinct
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.helpers import normalize
from src.webapp.database import get_db
from src.webapp.models import Product
from src.webapp.models.product import product_tg_categories  # ✅ association table

router = APIRouter(prefix="/search", tags=["search"])


def _parse_ids(csv: str | None) -> list[int]:
    if not csv:
        return []
    out: list[int] = []
    for x in csv.split(","):
        x = x.strip()
        if not x:
            continue
        out.append(int(x))
    return out


async def _filtered_product_ids_by_tg_categories(
        db: AsyncSession,
        *,
        tg_category_ids_csv: str | None,
        mode: str = "any",  # any|all
) -> list[int] | None:
    ids = _parse_ids(tg_category_ids_csv)
    if not ids:
        return None

    if mode not in ("any", "all"):
        mode = "any"

    if mode == "any":
        stmt = (
            select(distinct(product_tg_categories.c.product_id))
            .where(product_tg_categories.c.tg_category_id.in_(ids))
        )
        rows = (await db.execute(stmt)).scalars().all()
        return [int(x) for x in rows]

    # mode == "all"
    stmt = (
        select(product_tg_categories.c.product_id)
        .where(product_tg_categories.c.tg_category_id.in_(ids))
        .group_by(product_tg_categories.c.product_id)
        .having(func.count(distinct(product_tg_categories.c.tg_category_id)) == len(ids))
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [int(x) for x in rows]


async def search_products(
        db: AsyncSession,
        q: Optional[str],
        page: int,
        limit: int,
        tg_category_ids: Optional[str] = None,        # ✅ NEW
        tg_category_mode: str = "any",                # ✅ NEW any|all
):
    offset = page * limit
    filtered: list[dict] = []
    batch_size = 50
    skip = 0

    norm_q = await normalize(q) if q else None

    # ✅ NEW: if category filter present, precompute allowed product IDs
    allowed_product_ids = await _filtered_product_ids_by_tg_categories(
        db,
        tg_category_ids_csv=tg_category_ids,
        mode=tg_category_mode,
    )
    allowed_set = set(allowed_product_ids or [])

    while len(filtered) < offset + limit:
        stmt = (
            select(Product)
            .options(selectinload(Product.features))
            .offset(skip)
            .limit(batch_size)
        )

        # ✅ If filtering by tg categories, constrain DB query early
        if allowed_product_ids is not None:
            stmt = stmt.where(Product.id.in_(allowed_product_ids))

        result = await db.execute(stmt)
        batch = result.scalars().all()
        if not batch:
            break

        for product in batch:
            if not product.features:
                continue

            # ✅ additional safety (in case ORM offsets interact weirdly)
            if allowed_product_ids is not None and product.id not in allowed_set:
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

    # ✅ total should match filter
    if norm_q or (allowed_product_ids is not None):
        total = len(filtered)
    else:
        total = await db.scalar(select(func.count()).select_from(Product))

    return {"results": page_results, "total": total}


@router.get("/")
async def search(
        q: Optional[str] = Query(None),
        page: int = Query(0, ge=0),
        limit: int = Query(10, ge=1),

        # ✅ NEW query params
        tg_category_ids: Optional[str] = Query(None, description="CSV like '1,2,3'"),
        tg_category_mode: str = Query("any", pattern="^(any|all)$"),

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