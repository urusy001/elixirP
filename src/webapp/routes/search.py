from typing import Optional, List, Set, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.helpers import normalize
from src.webapp.database import get_db
from src.webapp.models import Product, Feature

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
        tg_category_ids: Optional[str] = None,
        tg_category_mode: Literal["any", "all"] = "any",
        sort_by: Literal["name", "price"] = "name",
        sort_dir: Literal["asc", "desc"] = "asc",
):
    offset = page * limit

    cat_ids = _parse_int_csv(tg_category_ids)
    allowed_onec_ids = await _allowed_product_onec_ids_by_tg_categories(
        db,
        tg_category_ids=cat_ids,
        mode=tg_category_mode,
    )

    # ---- subquery: per-product stock flag + price stats ----
    # has_stock = 1 if ANY feature has balance > 0, else 0
    has_stock = func.max(case((Feature.balance > 0, 1), else_=0)).label("has_stock")

    # price stats for sorting (use IN-STOCK features for price sort; out-of-stock => NULL => goes last)
    min_stock_price = func.min(case((Feature.balance > 0, Feature.price), else_=None)).label("min_stock_price")
    max_stock_price = func.max(case((Feature.balance > 0, Feature.price), else_=None)).label("max_stock_price")

    stats_sq = (
        select(
            Product.id.label("pid"),
            has_stock,
            min_stock_price,
            max_stock_price,
        )
        .select_from(Product)
        .join(Feature, Feature.product_id == Product.id, isouter=True)
        .group_by(Product.id)
        .subquery()
    )

    # ---- base statement ----
    stmt = (
        select(Product)
        .join(stats_sq, stats_sq.c.pid == Product.id)
        .options(selectinload(Product.features))
    )

    # filters
    if allowed_onec_ids is not None:
        stmt = stmt.where(Product.onec_id.in_(allowed_onec_ids))

    if q:
        # DB-side search (replace with your normalize strategy if you have normalized column)
        stmt = stmt.where(func.lower(Product.name).contains(q.lower()))

    # ---- ORDER BY: stock first, then requested sort ----
    # stock_rank: 0 for in-stock products, 1 for fully out-of-stock -> out-of-stock go last
    stock_rank = case((stats_sq.c.has_stock == 1, 0), else_=1)

    if sort_by == "price":
        if sort_dir == "asc":
            stmt = stmt.order_by(
                stock_rank,
                stats_sq.c.min_stock_price.nulls_last(),
                func.lower(Product.name).asc(),
            )
        else:
            stmt = stmt.order_by(
                stock_rank,
                stats_sq.c.max_stock_price.desc().nulls_last(),
                func.lower(Product.name).asc(),
            )
    else:
        if sort_dir == "asc":
            stmt = stmt.order_by(
                stock_rank,
                func.lower(Product.name).asc(),
                stats_sq.c.min_stock_price.nulls_last(),
            )
        else:
            stmt = stmt.order_by(
                stock_rank,
                func.lower(Product.name).desc(),
                stats_sq.c.min_stock_price.nulls_last(),
            )

    # page
    result = await db.execute(stmt.offset(offset).limit(limit))
    products = result.scalars().unique().all()

    # total
    total_stmt = (
        select(func.count())
        .select_from(
            select(Product.id)
            .join(stats_sq, stats_sq.c.pid == Product.id)
            .where(True)
            .correlate(None)
            .subquery()
        )
    )
    if allowed_onec_ids is not None:
        total_stmt = total_stmt.where(Product.onec_id.in_(allowed_onec_ids))
    if q:
        total_stmt = total_stmt.where(func.lower(Product.name).contains(q.lower()))

    total = await db.scalar(total_stmt)

    # response (keeps ALL features; product ordering already DB-driven)
    results = []
    for product in products:
        results.append(
            {
                "name": product.name,
                "onec_id": product.onec_id,
                "url": f"/product/{product.onec_id}",
                "image": "/static/images/product.png",
                "features": [
                    {
                        "id": f.onec_id,
                        "name": f.name,
                        "price": float(f.price) if f.price is not None else None,
                        "balance": getattr(f, "balance", 0) or 0,
                    }
                    for f in (product.features or [])
                ],
            }
        )

    return {"results": results, "total": int(total or 0)}



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