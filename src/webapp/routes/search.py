from typing import Optional, List, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.helpers import normalize
from src.webapp.database import get_db
from src.webapp.models import Product
from src.webapp.models.product_tg_categories import product_tg_categories

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
        return set((await db.execute(stmt)).scalars().all())

    # mode == "all"
    from sqlalchemy import func
    stmt = (
        select(product_tg_categories.c.product_onec_id)
        .where(product_tg_categories.c.tg_category_id.in_(tg_category_ids))
        .group_by(product_tg_categories.c.product_onec_id)
        .having(func.count(func.distinct(product_tg_categories.c.tg_category_id)) == len(tg_category_ids))
    )
    return set((await db.execute(stmt)).scalars().all())


def _min_max_price_from_features(features: list[dict]) -> tuple[float | None, float | None]:
    prices = [float(f["price"]) for f in features if float(f.get("balance") or 0) > 0]
    if not prices:
        return None, None
    return min(prices), max(prices)


async def search_products(
        db: AsyncSession,
        q: Optional[str],
        page: int,
        limit: int,
        tg_category_ids: Optional[list[int]] = None,
        tg_category_mode: Literal["any", "all"] = "any",
        sort_by: Literal["default", "alpha", "price"] = "default",
        sort_dir: Literal["asc", "desc"] = "asc",
):
    offset = page * limit

    norm_q = await normalize(q) if q else None

    allowed_onec_ids: Optional[set[str]] = None
    if tg_category_ids:
        allowed_onec_ids = await _filtered_product_onec_ids_by_tg_categories(
            db, tg_category_ids=tg_category_ids, mode=tg_category_mode
        )
        if not allowed_onec_ids:
            return {"results": [], "total": 0}

    filtered: list[dict] = []
    batch_size = 50
    skip = 0

    # IMPORTANT: for correct sorting + pagination, we must gather ALL matching items first.
    while True:
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

            features_payload = [
                {"id": f.onec_id, "name": f.name, "price": float(f.price), "balance": f.balance}
                for f in product.features
            ]

            filtered.append(
                {
                    "onec_id": product.onec_id,  # optional but useful
                    "name": product.name,
                    "url": f"/product/{product.onec_id}",
                    "image": "/static/images/product.png",
                    "features": features_payload,
                }
            )

        skip += batch_size

    # ---- SORTING ----
    reverse = (sort_dir == "desc")

    if sort_by == "alpha":
        filtered.sort(key=lambda x: (x.get("name") or "").strip().lower(), reverse=reverse)

    elif sort_by == "price":
        # Asc = lowest available price, Desc = highest available price
        def price_key(item: dict) -> float:
            mn, mx = _min_max_price_from_features(item.get("features") or [])
            if reverse:
                # Desc: highest price first; missing => very small so it sinks
                return mx if mx is not None else float("-inf")
            # Asc: lowest price first; missing => very large so it sinks
            return mn if mn is not None else float("inf")

        filtered.sort(key=price_key, reverse=False)  # reverse already encoded in key

    # else: default = keep DB order

    total = len(filtered)
    page_results = filtered[offset: offset + limit]
    return {"results": page_results, "total": total}


@router.get("")  # avoid 307 redirect
async def search(
        q: Optional[str] = Query(None),
        page: int = Query(0, ge=0),
        limit: int = Query(10, ge=1),

        tg_category_ids: Optional[List[int]] = Query(None),
        tg_category_mode: Literal["any", "all"] = Query("any"),

        sort_by: Literal["default", "alpha", "price"] = Query("default"),
        sort_dir: Literal["asc", "desc"] = Query("asc"),

        db: AsyncSession = Depends(get_db),
):
    return await search_products(
        db,
        q=q,
        page=page,
        limit=limit,
        tg_category_ids=tg_category_ids,
        tg_category_mode=tg_category_mode,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )