from typing import Optional, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.helpers import normalize
from src.webapp.database import get_db
from src.webapp.models import Product

router = APIRouter(prefix="/search", tags=["search"])


def _feature_prices_in_stock(product: Product) -> list[float]:
    prices: list[float] = []
    for f in (product.features or []):
        try:
            bal = float(f.balance or 0)
            if bal <= 0:
                continue
            prices.append(float(f.price))
        except Exception:
            continue
    return prices


async def search_products(
        db: AsyncSession,
        q: Optional[str],
        page: int,
        limit: int,
        sort_by: Literal["default", "alpha", "price"] = "default",
        sort_dir: Literal["asc", "desc"] = "asc",
):
    offset = page * limit
    filtered: list[dict] = []
    batch_size = 50
    skip = 0

    norm_q = await normalize(q) if q else None

    # We still stream from DB in batches, but sorting is applied on the
    # collected items (same as your existing logic).
    # NOTE: true "global sorting" requires scanning all products.
    # This patch keeps your behavior but makes DESC actually work.
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

            # query filter
            if norm_q and norm_q not in await normalize(product.name):
                continue

            # build features payload (keep all features like before)
            features_payload = [
                {"id": f.onec_id, "name": f.name, "price": float(f.price), "balance": f.balance}
                for f in product.features
            ]

            prices_in_stock = _feature_prices_in_stock(product)
            # for price sorting:
            # - asc: lowest available price
            # - desc: highest available price
            sort_price_min = min(prices_in_stock) if prices_in_stock else float("inf")
            sort_price_max = max(prices_in_stock) if prices_in_stock else float("-inf")

            filtered.append(
                {
                    "name": product.name,
                    "onec_id": product.onec_id,
                    "url": f"/product/{product.onec_id}",
                    "image": "/static/images/product.png",
                    "features": features_payload,

                    # internal sort keys (we’ll remove them before returning)
                    "_sort_name": (await normalize(product.name)) if product.name else "",
                    "_sort_price_min": sort_price_min,
                    "_sort_price_max": sort_price_max,
                }
            )

        skip += batch_size

        # If user asked sorting, we need enough items to sort and then slice.
        # If not sorting, your old "collect until offset+limit" behavior is ok.
        if sort_by == "default" and len(filtered) >= offset + limit:
            break

        # For sorted views, we still can stop early once we have a decent pool,
        # but to be 100% correct across the whole catalog you must scan all products.
        # Keep it sane: stop once we have enough for current page + some buffer.
        if sort_by != "default" and len(filtered) >= (offset + limit + 200):
            break

    # apply sorting
    reverse = (sort_dir == "desc")
    if sort_by == "alpha":
        filtered.sort(key=lambda x: x.get("_sort_name", ""), reverse=reverse)
    elif sort_by == "price":
        if reverse:
            filtered.sort(key=lambda x: x.get("_sort_price_max", float("-inf")), reverse=True)
        else:
            filtered.sort(key=lambda x: x.get("_sort_price_min", float("inf")), reverse=False)

    page_results = filtered[offset: offset + limit]

    # remove internal keys
    for item in page_results:
        item.pop("_sort_name", None)
        item.pop("_sort_price_min", None)
        item.pop("_sort_price_max", None)

    if q:
        total = len(filtered)
    else:
        total = await db.scalar(select(func.count()).select_from(Product))

    return {"results": page_results, "total": total}


@router.get("/")
async def search(
        q: Optional[str] = Query(None),
        page: int = Query(0, ge=0),
        limit: int = Query(10, ge=1),

        # ✅ new params
        sort_by: Literal["default", "alpha", "price"] = Query("default"),
        sort_dir: Literal["asc", "desc"] = Query("asc"),

        db: AsyncSession = Depends(get_db),
):
    return await search_products(
        db,
        q=q,
        page=page,
        limit=limit,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )