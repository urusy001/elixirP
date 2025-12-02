import logging
from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.webapp.crud import get_user  # from your CRUD functions
from src.webapp.database import get_db
from src.webapp.schemas import UserRead

router = APIRouter(prefix="/users", tags=["users"])

@router.get("", response_model=List[UserRead])
async def get_users(
        column_name: str = Query(..., description="Column name to filter by"),
        value: str = Query(..., description="Value for the column"),
        db: AsyncSession = Depends(get_db),
):
    user = await get_user(db, column_name, value)
    logging.info('131231232132131232123123123131' if user else '0.112121321321313213321')
    if not user: return []
    else: return [user]
