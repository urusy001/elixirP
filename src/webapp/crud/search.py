from typing import Literal, Optional
from sqlalchemy import func, case, select, bindparam, String, cast
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.helpers import normalize, normalize_user_value
from src.webapp.models import Product, product_tg_categories, User


def _parse_int_csv(value: Optional[str]) -> list[int]:
    if not value: return []
    parts = [p.strip() for p in value.split(",") if p.strip()]
    out: list[int] = []
    for p in parts:
        try: out.append(int(p))
        except ValueError: continue

    seen = set()
    res = []
    for x in out:
        if x not in seen:
            seen.add(x)
            res.append(x)
    return res


async def _allowed_product_onec_ids_by_tg_categories(db: AsyncSession, tg_category_ids: list[int],
                                                     mode: Literal["any", "all"] = "any") -> Optional[set[str]]:
    if not tg_category_ids: return None
    if mode == "all":
        stmt = (select(product_tg_categories.c.product_onec_id).where(
            product_tg_categories.c.tg_category_id.in_(tg_category_ids)).group_by(
            product_tg_categories.c.product_onec_id).having(
            func.count(func.distinct(product_tg_categories.c.tg_category_id)) == len(tg_category_ids)))
    else:
        stmt = (select(product_tg_categories.c.product_onec_id).where(
            product_tg_categories.c.tg_category_id.in_(tg_category_ids)).distinct())
    rows = (await db.execute(stmt)).scalars().all()
    return set(rows)


async def search_products(db: AsyncSession, q: Optional[str], page: int, limit: int,
                          tg_category_ids: Optional[str] = None, tg_category_mode: Literal["any", "all"] = "any",
                          sort_by: Literal["name", "price"] = "name", sort_dir: Literal["asc", "desc"] = "asc"):
    offset = page * limit
    filtered = []
    batch_size = 60
    skip = 0
    norm_q = await normalize(q) if q else None
    cat_ids = _parse_int_csv(tg_category_ids)
    allowed_onec_ids = await _allowed_product_onec_ids_by_tg_categories(db, tg_category_ids=cat_ids,
                                                                        mode=tg_category_mode)
    Feature = Product.features.property.mapper.class_
    stats_sq = select(Product.id.label("pid"), func.max(case((Feature.balance > 0, 1), else_=0)).label("has_stock"),
                      func.min(case((Feature.balance > 0, Feature.price), else_=None)).label("min_stock_price"),
                      func.max(case((Feature.balance > 0, Feature.price), else_=None)).label(
                          "max_stock_price")).select_from(Product).join(Feature, Product.features,
                                                                        isouter=True).group_by(Product.id).subquery()
    stock_rank = case((stats_sq.c.has_stock == 1, 0), else_=1)

    def ordered_stmt():
        stmt = select(Product).join(stats_sq, stats_sq.c.pid == Product.id).options(selectinload(Product.features))
        if allowed_onec_ids is not None: stmt = stmt.where(Product.onec_id.in_(allowed_onec_ids))
        if sort_by == "price":
            if sort_dir == "asc":
                stmt = stmt.order_by(stock_rank, stats_sq.c.min_stock_price.nulls_last(),
                                     func.lower(Product.name).asc())
            else:
                stmt = stmt.order_by(stock_rank, stats_sq.c.max_stock_price.desc().nulls_last(),
                                     func.lower(Product.name).asc())

        else:
            if sort_dir == "asc":
                stmt = stmt.order_by(stock_rank, func.lower(Product.name).asc(),
                                     stats_sq.c.min_stock_price.nulls_last())
            else:
                stmt = stmt.order_by(stock_rank, func.lower(Product.name).desc(),
                                     stats_sq.c.min_stock_price.nulls_last())

        return stmt

    while True:
        stmt = ordered_stmt().offset(skip).limit(batch_size)
        result = await db.execute(stmt)
        batch = result.scalars().all()
        if not batch: break
        for product in batch:
            if norm_q and norm_q not in await normalize(product.name): continue
            all_features = list(product.features or [])
            in_stock_features = [f for f in all_features if (getattr(f, "balance", 0) or 0) > 0]
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
                        {
                            "id": f.onec_id,
                            "name": f.name,
                            "price": float(f.price) if f.price is not None else None,
                            "balance": getattr(f, "balance", 0) or 0,
                        }
                        for f in all_features
                    ],
                }
            )

        skip += batch_size

    page_results = filtered[offset: offset + limit]
    if q or cat_ids:
        total = len(filtered)
    else:
        total = await db.scalar(select(func.count()).select_from(Product))

    for item in page_results:
        item.pop("min_price", None)
        item.pop("max_price", None)

    return {"results": page_results, "total": total}


async def search_users(db: AsyncSession, by: str, value: str, page: Optional[int] = None, limit: Optional[int] = None) -> tuple[list[User], int]:
    stmt = select(User)

    if by is not None:
        column = getattr(User, by, None)
        if column is None: return [], 0

        norm_value = normalize_user_value(by, value)
        if norm_value is None or str(norm_value).strip() == "": return [], 0

        # universal: for ANY column type
        # 1) try exact match if we can coerce (keeps indexes for ints/bools/etc)
        # 2) fallback to contains by casting to text (works for bigint/date/numeric/etc)
        try: py_t = column.type.python_type
        except Exception: py_t = None

        coerced = None
        if py_t is not None and py_t is not str:
            try: coerced = py_t(norm_value)
            except Exception: coerced = None

        if coerced is not None: stmt = stmt.where(column == bindparam("v_exact", coerced, type_=column.type))
        else: stmt = stmt.where(cast(column, String).ilike(bindparam("v", f"%{norm_value}%", type_=String())))

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = await db.scalar(count_stmt)

    stmt = stmt.order_by(User.tg_id.desc())
    if limit is not None: stmt = stmt.limit(limit)
    if page is not None and limit is not None: stmt = stmt.offset(page * limit)

    rows = (await db.execute(stmt)).scalars().all()
    return rows, int(total or 0)
