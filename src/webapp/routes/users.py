from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.webapp.crud import get_user
from src.webapp.database import get_db

router = APIRouter(prefix="/users", tags=["users"])

@router.get("")
async def get_users(
        column_name: str = Query(..., description="Column name to filter by"),
        value: str = Query(..., description="Value for the column"),
        db: AsyncSession = Depends(get_db),
):
    if column_name in ["tg_id"]:
        user = await get_user(db, column_name, value)
        return user

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
