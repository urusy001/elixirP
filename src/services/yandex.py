from __future__ import annotations

import asyncio
import io
import logging
import pandas as pd
import httpx

from urllib.parse import quote
from decimal import Decimal
from typing import Any
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.webapp import get_session
from src.webapp.models.promo_code import PromoCode
from config import YANDEX_DISK_OAUTH_TOKEN

logger = logging.getLogger("promo_codes")
D0 = Decimal("0.00")

def _clean_str(v: Any) -> str | None:
    if v is None or (isinstance(v, float) and pd.isna(v)) or pd.isna(v): return None
    s = str(v).strip()
    return s or None


def _to_decimal(v: Any, default: Decimal = D0) -> Decimal:
    if v is None or (isinstance(v, float) and pd.isna(v)) or pd.isna(v): return default
    if isinstance(v, Decimal): return v
    s = str(v).strip()
    if not s: return default
    s = s.replace("%", "").replace(",", ".").strip()
    try: return Decimal(s)
    except Exception: return default


async def get_first_sheet_df() -> pd.DataFrame:
    base = "https://webdav.yandex.ru"
    url = base + quote("/Для менеджеров/Промокод Бонусная программа.xlsx", safe="/")
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.get(url, headers={"Authorization": f"OAuth {YANDEX_DISK_OAUTH_TOKEN}"})
        r.raise_for_status()
    df = pd.read_excel(
        io.BytesIO(r.content),
        sheet_name=0,
        engine="openpyxl",
        header=None,
        skiprows=2,
        usecols="A:J",
    )
    return df


async def update_promo_codes(db: AsyncSession) -> dict[str, int]:
    df = await get_first_sheet_df()
    promos_by_code: dict[str, dict[str, Any]] = {}

    for _, row in df.iterrows():
        code = _clean_str(row.iloc[0])  # A
        if not code:
            continue

        rec = {
            "code": code,
            "discount_pct": _to_decimal(row.iloc[3], D0),  # D
            "owner_pct": _to_decimal(row.iloc[4], D0),     # E
            "owner_name": _clean_str(row.iloc[5]) or "UNKNOWN",  # F
            "lvl1_pct": _to_decimal(row.iloc[6], D0),      # G
            "lvl1_name": _clean_str(row.iloc[7]),          # H
            "lvl2_pct": _to_decimal(row.iloc[8], D0),      # I
            "lvl2_name": _clean_str(row.iloc[9]),          # J
        }

        promos_by_code[code] = rec

    file_codes = set(promos_by_code.keys())
    if not file_codes: return {"created": 0, "updated": 0, "deleted": 0}
    res = await db.execute(select(PromoCode).where(PromoCode.code.in_(file_codes)))
    existing = res.scalars().all()
    existing_by_code = {p.code: p for p in existing}

    created = 0
    updated = 0

    for code, rec in promos_by_code.items():
        obj = existing_by_code.get(code)
        if obj is None:
            obj = PromoCode(
                code=rec["code"],
                discount_pct=rec["discount_pct"],
                owner_name=rec["owner_name"],
                owner_pct=rec["owner_pct"],

                lvl1_name=rec["lvl1_name"],
                lvl1_pct=rec["lvl1_pct"],

                lvl2_name=rec["lvl2_name"],
                lvl2_pct=rec["lvl2_pct"],

                # counters start at 0:
                times_used=0,
                owner_amount_gained=D0,
                lvl1_amount_gained=D0,
                lvl2_amount_gained=D0,
            )
            db.add(obj)
            created += 1
            continue

        changed = False
        for field in ("discount_pct", "owner_name", "owner_pct", "lvl1_name", "lvl1_pct", "lvl2_name", "lvl2_pct"):
            new_val = rec[field]
            if getattr(obj, field) != new_val:
                setattr(obj, field, new_val)
                changed = True
        if changed: updated += 1

    # ✅ delete codes not in file
    del_res = await db.execute(delete(PromoCode).where(~PromoCode.code.in_(file_codes)))
    deleted = int(del_res.rowcount or 0)

    await db.commit()
    return {"created": created, "updated": updated, "deleted": deleted}

async def promo_codes_worker():
    while True:
        logger.info("Started updating promo codes")
        async with get_session() as session: result = await update_promo_codes(session)
        logger.info(f"Created: {result['created']}, updated: {result['updated']} and deleted {result['deleted']} promo codes, sleeping for a day")
        await asyncio.sleep(24*3600)

if __name__ == "__main__":
    asyncio.run(promo_codes_worker())
