from datetime import date
from typing import List, Dict, Tuple, Optional, Literal
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from src.webapp.models import UserTokenUsage, User

BotLiteral = Literal["dose", "professor", "new"]

async def get_usages(
    db: AsyncSession,
    start_date: date,
    end_date: Optional[date] = None,
    bot: Optional[BotLiteral] = None,  # ⬅️ separate variable for bot
) -> Tuple[str, List[Dict[str, float]]]:

    end_date = end_date or date.today()
    if end_date < start_date:
        raise ValueError("end_date cannot be earlier than start_date")

    where_clauses = [
        UserTokenUsage.date >= start_date,
        UserTokenUsage.date <= end_date,
    ]
    if bot:
        where_clauses.append(UserTokenUsage.bot == bot)

    stmt = (
        select(
            UserTokenUsage.user_id,
            User.tg_phone,
            func.count(UserTokenUsage.id).label("total_requests"),
            func.coalesce(func.sum(UserTokenUsage.input_tokens), 0).label("input_tokens"),
            func.coalesce(func.sum(UserTokenUsage.output_tokens), 0).label("output_tokens"),
            func.coalesce(func.sum(UserTokenUsage.input_cost_usd), 0).label("input_cost_usd"),
            func.coalesce(func.sum(UserTokenUsage.output_cost_usd), 0).label("output_cost_usd"),
        )
        .join(User, UserTokenUsage.user_id == User.tg_id)
        .where(*where_clauses)
        .group_by(UserTokenUsage.user_id, User.tg_phone)
    )

    period_label = f"С {start_date:%Y-%m-%d} по {end_date:%Y-%m-%d}" + (f" (бот: {bot})" if bot else "")

    result = await db.execute(stmt)
    rows = result.all()

    usage_list: List[Dict[str, float]] = []
    for row in rows:
        input_tokens = int(row.input_tokens)
        output_tokens = int(row.output_tokens)
        total_tokens = input_tokens + output_tokens

        input_cost = float(row.input_cost_usd)
        output_cost = float(row.output_cost_usd)
        total_cost = input_cost + output_cost

        total_requests = int(row.total_requests)
        avg_cost = round(total_cost / total_requests, 4) if total_requests else 0.0

        usage_list.append({
            "Айди Телеграм": row.user_id,
            "Номер Телеграм": row.tg_phone,
            "Входящие токены": input_tokens,
            "Исходящие токены": output_tokens,
            "Всего токенов": total_tokens,
            "Всего запросов": total_requests,
            "Стоимость входящих в $": round(input_cost, 2),
            "Стоимость исходящих в $": round(output_cost, 2),
            "Стоимость всего в $": round(total_cost, 2),
            "Средняя стоимость запроса": avg_cost,
        })

    return period_label, usage_list

from datetime import date
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Literal
from src.webapp.models import UserTokenUsage, BotEnum

BotLiteral = Literal["dose", "professor", "new"]

async def write_usage(
    db: AsyncSession,
    user_id: int,
    input_tokens: int,
    output_tokens: int,
    bot: BotLiteral,  # ⬅️ separate param
    usage_date: Optional[date] = None,
):
    """
    Create or increment token usage for (user_id, date, bot).
    """
    usage_date = usage_date or date.today()

    result = await db.execute(
        select(UserTokenUsage).where(
            UserTokenUsage.user_id == user_id,
            UserTokenUsage.date == usage_date,
            UserTokenUsage.bot == BotEnum(bot),  # Enum cast
        )
    )
    usage = result.scalar_one_or_none()

    if usage:
        # triggers @validates to recompute costs
        usage.input_tokens += input_tokens
        usage.output_tokens += output_tokens
    else:
        usage = UserTokenUsage(
            user_id=user_id,
            date=usage_date,
            bot=BotEnum(bot),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        db.add(usage)

    await db.commit()
    await db.refresh(usage)
    return usage