from datetime import date
from typing import Dict, Optional, List, Tuple, Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.webapp.models import BotEnum, UserTokenUsage, User
from src.webapp.schemas import BotLiteral


async def get_usages(
        db: AsyncSession,
        start_date: date,
        end_date: Optional[date] = None,
        bot: Optional[BotLiteral] = None,
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
            func.coalesce(func.sum(UserTokenUsage.total_requests), 0).label("total_requests"),  # ⬅️ changed
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
    if bot == "new":  # gpt-4.1
        input_per_m = 2.00
        output_per_m = 8.00
    elif bot in ["dose", "professor"]:  # gpt-4.1-mini
        input_per_m = 0.40
        output_per_m = 1.60
    else:
        input_per_m = 0.40
        output_per_m = 1.60

    for row in rows:
        input_tokens = int(row.input_tokens)
        output_tokens = int(row.output_tokens)
        total_tokens = input_tokens + output_tokens

        input_cost = (input_tokens / 1_000_000) * input_per_m
        output_cost = (output_tokens / 1_000_000) * output_per_m
        total_cost = input_cost + output_cost

        total_requests = int(row.total_requests)  # ⬅️ now sum from DB
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

async def write_usage(
        db: AsyncSession,
        user_id: int,
        input_tokens: int,
        output_tokens: int,
        bot: BotLiteral,
        usage_date: Optional[date] = None,
):
    """
    Create or increment token usage for (user_id, date, bot).
    Every call is treated as 1 request.
    """
    usage_date = usage_date or date.today()

    result = await db.execute(
        select(UserTokenUsage).where(
            UserTokenUsage.user_id == user_id,
            UserTokenUsage.date == usage_date,
            UserTokenUsage.bot == BotEnum(bot),
            )
    )
    usage = result.scalar_one_or_none()

    if usage:
        # triggers @validates to recompute costs
        usage.input_tokens += input_tokens
        usage.output_tokens += output_tokens
        usage.total_requests = (usage.total_requests or 0) + 1   # ⬅️ increment
    else:
        usage = UserTokenUsage(
            user_id=user_id,
            date=usage_date,
            bot=BotEnum(bot),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_requests=1,  # ⬅️ first request for this day/bot
        )
        db.add(usage)

    await db.commit()
    await db.refresh(usage)
    return usage

async def get_user_usage_totals(db: AsyncSession, user_id: int, start_date: Optional[date] = None, end_date: Optional[date] = None) -> Dict[str, Any]:
    """
    Return total usage sums for a single user grouped by bot, plus grand totals.
    Costs are summed from DB columns: input_cost_usd/output_cost_usd.
    """
    end_date = end_date or date.today()
    where_clauses = [UserTokenUsage.user_id == user_id]
    if start_date:
        if end_date < start_date: raise ValueError("end_date cannot be earlier than start_date")
        where_clauses += [UserTokenUsage.date >= start_date, UserTokenUsage.date <= end_date]
    else: where_clauses += [UserTokenUsage.date <= end_date]

    tg_phone = await db.scalar(select(User.tg_phone).where(User.tg_id == user_id))

    stmt = (
        select(
            UserTokenUsage.bot.label("bot"),
            func.coalesce(func.sum(UserTokenUsage.total_requests), 0).label("total_requests"),
            func.coalesce(func.sum(UserTokenUsage.input_tokens), 0).label("input_tokens"),
            func.coalesce(func.sum(UserTokenUsage.output_tokens), 0).label("output_tokens"),
            func.coalesce(func.sum(UserTokenUsage.input_cost_usd), 0).label("input_cost_usd"),
            func.coalesce(func.sum(UserTokenUsage.output_cost_usd), 0).label("output_cost_usd"),
        )
        .where(*where_clauses)
        .group_by(UserTokenUsage.bot)
        .order_by(UserTokenUsage.bot)
    )

    rows = (await db.execute(stmt)).all()

    by_bot: List[Dict[str, Any]] = []
    grand_requests = grand_in = grand_out = 0
    grand_in_cost = grand_out_cost = 0.0

    for r in rows:
        in_tokens = int(r.input_tokens)
        out_tokens = int(r.output_tokens)
        reqs = int(r.total_requests)

        in_cost = float(r.input_cost_usd or 0)
        out_cost = float(r.output_cost_usd or 0)
        total_cost = in_cost + out_cost

        bot_name = getattr(r.bot, "value", str(r.bot))  # BotEnum -> "new"/"dose"/...

        by_bot.append({
            "bot": bot_name,
            "total_requests": reqs,
            "input_tokens": in_tokens,
            "output_tokens": out_tokens,
            "total_tokens": in_tokens + out_tokens,
            "input_cost_usd": round(in_cost, 4),
            "output_cost_usd": round(out_cost, 4),
            "total_cost_usd": round(total_cost, 4),
            "avg_cost_per_request": round(total_cost / reqs, 6) if reqs else 0.0,
        })

        grand_requests += reqs
        grand_in += in_tokens
        grand_out += out_tokens
        grand_in_cost += in_cost
        grand_out_cost += out_cost

    totals = {
        "total_requests": grand_requests,
        "input_tokens": grand_in,
        "output_tokens": grand_out,
        "total_tokens": grand_in + grand_out,
        "input_cost_usd": round(grand_in_cost, 4),
        "output_cost_usd": round(grand_out_cost, 4),
        "total_cost_usd": round(grand_in_cost + grand_out_cost, 4),
        "avg_cost_per_request": round((grand_in_cost + grand_out_cost) / grand_requests, 6) if grand_requests else 0.0,
    }

    period_label = (
        f"С {start_date:%Y-%m-%d} по {end_date:%Y-%m-%d}"
        if start_date else
        f"До {end_date:%Y-%m-%d}"
    )

    return {
        "period": period_label,
        "user_id": user_id,
        "tg_phone": tg_phone,
        "by_bot": by_bot,
        "totals": totals,
    }