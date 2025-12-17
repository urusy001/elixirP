from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.webapp.database import get_db
from src.webapp.crud.tg_category import (
    list_tg_categories,
    list_products_by_tg_category_name,
)
from src.webapp.schemas.tg_category import TgCategoryRead
from src.webapp.schemas.product import ProductRead

router = APIRouter(prefix="/api/v1/public", tags=["public"])


@router.get("/tg-categories", response_model=list[TgCategoryRead])
async def public_list_tg_categories(db: AsyncSession = Depends(get_db)):
    return await list_tg_categories(db)


@router.get("/tg-categories/products", response_model=list[ProductRead])
async def public_list_products_by_category_name(
        name: str = Query(..., min_length=1, description="TG category name (can contain spaces)"),
        db: AsyncSession = Depends(get_db),
):
    return await list_products_by_tg_category_name(db, name)