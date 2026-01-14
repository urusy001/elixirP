from typing import Optional, Literal
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.webapp.crud.search import search_products
from src.webapp.database import get_db

router = APIRouter(prefix="/search", tags=["search"])

@router.get("/products")
async def search(q: Optional[str] = Query(None), page: int = Query(0, ge=0), limit: int = Query(10, ge=1), tg_category_ids: Optional[str] = Query(None, description="CSV: 1,2,3"), tg_category_mode: Literal["any", "all"] = Query("any"), sort_by: Literal["name", "price"] = Query("name"), sort_dir: Literal["asc", "desc"] = Query("asc"), db: AsyncSession = Depends(get_db)): return await search_products(db, q=q, page=page, limit=limit, tg_category_ids=tg_category_ids, tg_category_mode=tg_category_mode, sort_by=sort_by, sort_dir=sort_dir)


