from typing import Optional, List, Set, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.helpers import normalize
from src.webapp.database import get_db
from src.webapp.models import Product

# IMPORTANT:
# This must be a SQLAlchemy Table named `product_tg_categories` with columns:
# - product_onec_id (string)
# - tg_category_id (int)
from src.webapp.models.product_tg_categories import product_tg_categories

router = APIRouter(prefix="/search", tags=["search"])


def _parse_int_csv(value: Optional[str]) -> List[int]:
    if not value:
        return []
    parts = [p.strip() for p in value.split(",") if p.strip()]
    out: List[int] = []
    for p in parts:
        try:
            out.append(int(p))
        except ValueError:
            continue
    # unique, stable
    seen = set()
    res = []
    for x in out:
        if x not in seen:
            seen.add(x)
            res.append(x)
    return res


async def _allowed_product_onec_ids_by_tg_categories(
        db: AsyncSession,
        tg_category_ids: List[int],
        mode: Literal["any", "all"] = "any",
) -> Optional[Set[str]]:
    """
    Returns set of Product.onec_id allowed by tg categories filter.
    If tg_category_ids is empty -> None (no filter).
    """
    if not tg_category_ids:
        return None

    if mode == "all":
        # product must be linked to ALL selected categories
        stmt = (
            select(product_tg_categories.c.product_onec_id)
            .where(product_tg_categories.c.tg_category_id.in_(tg_category_ids))
            .group_by(product_tg_categories.c.product_onec_id)
            .having(func.count(func.distinct(product_tg_categories.c.tg_category_id)) == len(tg_category_ids))
        )
    else:
        # any
        stmt = (
            select(product_tg_categories.c.product_onec_id)
            .where(product_tg_categories.c.tg_category_id.in_(tg_category_ids))
            .distinct()
        )

    rows = (await db.execute(stmt)).scalars().all()
    return set(rows)


async def search_products(
        db: AsyncSession,
        q: Optional[str],
        page: int,
        limit: int,
        tg_category_ids: Optional[str] = None,          # csv: "1,2,3"
        tg_category_mode: Literal["any", "all"] = "any",
        sort_by: Literal["name", "price"] = "name",
        sort_dir: Literal["asc", "desc"] = "asc",
):
    offset = page * limit
    filtered = []
    batch_size = 60
    skip = 0

    norm_q = await normalize(q) if q else None
    cat_ids = _parse_int_csv(tg_category_ids)

    allowed_onec_ids = await _allowed_product_onec_ids_by_tg_categories(
        db,
        tg_category_ids=cat_ids,
        mode=tg_category_mode,
    )

    # We keep your original "batch scan + python filter" approach,
    # but now:
    # - category filter is applied
    # - sorting happens AFTER collecting
    # - price sort uses min for asc / max for desc over IN-STOCK features
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
            if allowed_onec_ids is not None and product.onec_id not in allowed_onec_ids:
                continue

            if not product.features:
                continue

            # only keep products with at least 1 in-stock feature
            in_stock_features = [f for f in product.features if (getattr(f, "balance", 0) or 0) > 0]
            if not in_stock_features:
                continue

            if norm_q:
                if norm_q not in await normalize(product.name):
                    continue

            prices = [float(f.price) for f in in_stock_features if f.price is not None]
            min_price = min(prices) if prices else 0.0
            max_price = max(prices) if prices else 0.0

            filtered.append(
                {
                    "name": product.name,
                    "onec_id": product.onec_id,
                    "url": f"/product/{product.onec_id}",
                    "image": "/static/images/product.png",
                    "min_price": min_price,
                    "max_price": max_price,
                    "features": [
                        {"id": f.onec_id, "name": f.name, "price": float(f.price), "balance": f.balance}
                        for f in product.features
                    ],
                }
            )

        skip += batch_size

    # SORT (global, not per-page)
    if sort_by == "price":
        # user requirement:
        # asc -> lowest price (min_price)
        # desc -> highest price (max_price)
        if sort_dir == "asc":
            filtered.sort(key=lambda x: (x.get("min_price", 0.0), x.get("name", "")))
        else:
            filtered.sort(key=lambda x: (-(x.get("max_price", 0.0)), x.get("name", "")))
    else:
        # name
        if sort_dir == "asc":
            filtered.sort(key=lambda x: (x.get("name", "").lower(), x.get("min_price", 0.0)))
        else:
            filtered.sort(key=lambda x: (x.get("name", "").lower()), reverse=True)

    page_results = filtered[offset: offset + limit]

    # keep your old total behavior
    if q or cat_ids:
        total = len(filtered)
    else:
        total = await db.scalar(select(func.count()).select_from(Product))

    # remove helper fields from response
    for item in page_results:
        item.pop("min_price", None)
        item.pop("max_price", None)

    return {"results": page_results, "total": total}


# ✅ NO redirect anymore:
@router.get("")
@router.get("/")
async def search(
        q: Optional[str] = Query(None),
        page: int = Query(0, ge=0),
        limit: int = Query(10, ge=1),

        # categories:
        tg_category_ids: Optional[str] = Query(None, description="CSV: 1,2,3"),
        tg_category_mode: Literal["any", "all"] = Query("any"),

        # sort:
        sort_by: Literal["name", "price"] = Query("name"),
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