from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.webapp.database import get_db
from src.webapp.crud.tg_category import (
    list_tg_categories,
)
from src.webapp.schemas.tg_category import TgCategoryRead

router = APIRouter(prefix="/tg-categories", tags=["public"])


@router.get("/", response_model=list[TgCategoryRead])
async def get_categories(db: AsyncSession = Depends(get_db)):
    rows = await list_tg_categories(db)
    out: list[TgCategoryRead] = []
    for r in rows:
        cat = r["category"]
        out.append(
            TgCategoryRead(
                id=cat.id,
                name=cat.name,
                description=cat.description,
                product_count=r["product_count"],
            )
        )
    return out