from datetime import date
from typing import List, Dict, Tuple
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from src.webapp.models import UserTokenUsage, User


async def get_usages(
    db: AsyncSession,
    start_date: date,
    end_date: date | None = None,
) -> Tuple[str, List[Dict[str, float]]]:
    """
    Get total usage grouped by user (joined with phone from users table)
    between start_date and end_date (inclusive).

    Args:
        db: AsyncSession — active DB session
        start_date: date — starting date (required)
        end_date: date | None — optional, defaults to today

    Returns:
        (
            period_label: str,  # e.g. "С 2025-10-01 по 2025-10-11"
            [
                {
                    "Айди Телеграм": int,
                    "Номер Телеграм": str,
                    "Входящие токены": int,
                    "Исходящие токены": int,
                    "Всего токенов": int,
                    "Стоимость входящих в $": float,
                    "Стоимость исходящих в $": float,
                    "Стоимость всего в $": float
                }, ...
            ]
        )
    """

    end_date = end_date or date.today()

    # --- Validate date order ---
    if end_date < start_date:
        raise ValueError("end_date cannot be earlier than start_date")

    # --- Base query with join to users ---
    stmt = (
        select(
            UserTokenUsage.user_id,
            User.tg_phone,
            func.sum(UserTokenUsage.input_tokens).label("input_tokens"),
            func.sum(UserTokenUsage.output_tokens).label("output_tokens"),
            func.sum(UserTokenUsage.input_cost_usd).label("input_cost_usd"),
            func.sum(UserTokenUsage.output_cost_usd).label("output_cost_usd"),
        )
        .join(User, UserTokenUsage.user_id == User.tg_id)
        .where(
            UserTokenUsage.date >= start_date,
            UserTokenUsage.date <= end_date,
        )
        .group_by(UserTokenUsage.user_id, User.tg_phone)
    )

    # --- Build label like "С 2025-10-01 по 2025-10-11" ---
    period_label = f"С {start_date.strftime('%Y-%m-%d')} по {end_date.strftime('%Y-%m-%d')}"

    # --- Execute ---
    result = await db.execute(stmt)
    rows = result.all()

    # --- Build list of dicts for Excel / reporting ---
    usage_list = [
        {
            "Айди Телеграм": row.user_id,
            "Номер Телеграм": row.tg_phone,
            "Входящие токены": row.input_tokens or 0,
            "Исходящие токены": row.output_tokens or 0,
            "Всего токенов": (row.input_tokens or 0) + (row.output_tokens or 0),
            "Стоимость входящих в $": round(row.input_cost_usd or 0, 2),
            "Стоимость исходящих в $": round(row.output_cost_usd or 0, 2),
            "Стоимость всего в $": round((row.input_cost_usd or 0) + (row.output_cost_usd or 0), 2),
        }
        for row in rows
    ]

    return period_label, usage_list

async def write_usage(
    db: AsyncSession,
    user_id: int,
    input_tokens: int,
    output_tokens: int,
    usage_date: date | None = None,
):
    """
    Create or update (increment) token usage for a user on a given date.
    """
    usage_date = usage_date or date.today()

    result = await db.execute(
        select(UserTokenUsage).where(
            UserTokenUsage.user_id == user_id,
            UserTokenUsage.date == usage_date,
        )
    )
    usage = result.scalar_one_or_none()

    if usage:
        usage.input_tokens += input_tokens
        usage.output_tokens += output_tokens
    else:
        usage = UserTokenUsage(
            user_id=user_id,
            date=usage_date,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        db.add(usage)

    await db.commit()
    await db.refresh(usage)
    return usage
