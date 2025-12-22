from __future__ import annotations

import asyncio
import json
import logging
import xml.etree.ElementTree as ET
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

import aiofiles
import httpx
from sqlalchemy.dialects.postgresql import insert as pg_insert

from config import ENTERPRISE_URL, ENTERPRISE_LOGIN, ENTERPRISE_PASSWORD
from src.onec import endpoints, keywords
from src.webapp import get_session
from src.webapp.database import get_db_items

UPSERT_BATCH_SIZE = 500
SLEEP_INTERVAL = 900  # 15 min


def _dec(v: Any, default: str = "0") -> Decimal:
    if v is None:
        return Decimal(default)
    s = str(v).strip()
    if not s:
        return Decimal(default)
    # 1C can return comma decimals sometimes
    s = s.replace(",", ".")
    try:
        return Decimal(s)
    except Exception:
        return Decimal(default)


class OneCEnterprise:
    NS = {
        "m": "http://schemas.microsoft.com/ado/2007/08/dataservices/metadata",
        "d": "http://schemas.microsoft.com/ado/2007/08/dataservices",
        "atom": "http://www.w3.org/2005/Atom",
    }

    def __init__(self, url=ENTERPRISE_URL, username=ENTERPRISE_LOGIN, password=ENTERPRISE_PASSWORD):
        limits = httpx.Limits(max_connections=20, max_keepalive_connections=10)
        self.__client = httpx.AsyncClient(
            auth=(username, password),
            limits=limits,
            timeout=httpx.Timeout(30.0),
        )
        self.__url = url
        self.log = logging.getLogger(self.__class__.__name__)

    # --------------------------------------------------------------------------
    #                          FETCHING FROM 1C
    # --------------------------------------------------------------------------

    async def __fetch_odata(self, endpoint: str, save: bool = False) -> list[dict[str, Any]]:
        url = f"{self.__url}{endpoint}"
        response = None

        for attempt in range(3):
            try:
                response = await self.__client.get(url)
                response.raise_for_status()
                if response.status_code == httpx.codes.OK:
                    break
            except Exception as e:
                self.log.warning(f"⚠️ Attempt {attempt + 1} failed for {url}: {e}")
                await asyncio.sleep(3)

        if not response:
            raise RuntimeError(f"❌ Failed to fetch {url} after 3 attempts")

        root = ET.fromstring(response.content)
        entries: list[dict[str, Any]] = []

        for entry in root.findall("atom:entry", self.NS):
            content = entry.find("atom:content/m:properties", self.NS)
            if content is None:
                continue

            record: dict[str, Any] = {}
            for elem in content:
                tag = elem.tag.split("}", 1)[1] if "}" in elem.tag else elem.tag

                if tag == "ДополнительныеРеквизиты":
                    extras = []
                    for extra in elem.findall("d:element", self.NS):
                        extra_record = {sub.tag.split("}", 1)[1]: sub.text for sub in extra}
                        extras.append(extra_record)
                    record[tag] = extras
                else:
                    record[tag] = elem.text

            entries.append(record)

        if save:
            fname = f"{endpoint.split('?')[0]}.json"
            async with aiofiles.open(fname, "w", encoding="utf-8") as f:
                await f.write(json.dumps(entries, ensure_ascii=False, indent=4))
            self.log.info(f"🧾 Saved {fname}")

        return entries

    async def get_units_1c(self, save: bool = False) -> dict[str, dict[str, Any]]:
        units = await self.__fetch_odata(endpoints.UNITS, save)
        return {
            u.get("Ref_Key"): {
                "onec_id": u.get("Ref_Key"),
                "name": u.get("Description"),
                "description": u.get("НаименованиеПолное"),
            }
            for u in units
            if u.get("DeletionMark") not in [True, "true"]
        }

    async def get_categories_1c(self, save: bool = False) -> dict[str, dict[str, Any]]:
        cats = await self.__fetch_odata(endpoints.CATEGORIES, save)
        return {
            c.get("Ref_Key"): {
                "onec_id": c.get("Ref_Key"),
                "unit_onec_id": (
                    None
                    if c.get("ЕдиницаИзмерения_Key") == "00000000-0000-0000-0000-000000000000"
                    else c.get("ЕдиницаИзмерения_Key")
                ),
                "name": c.get("Description", "Без категории"),
                "code": c.get("Code"),
            }
            for c in cats
            if c.get("DeletionMark") not in [True, "true"]
        }

    async def get_prices_1c(self, save: bool = False) -> dict[str, dict[str, Any]]:
        prices = await self.__fetch_odata(endpoints.PRICES, save)
        latest: dict[tuple[str, str], dict[str, Any]] = {}

        for entry in prices:
            key = (entry["Номенклатура_Key"], entry["Характеристика_Key"])
            entry_period = datetime.fromisoformat(entry["Period"])
            if key not in latest or entry_period > datetime.fromisoformat(latest[key]["Period"]):
                latest[key] = entry

        return {
            f"{v['Номенклатура_Key']}_{v['Характеристика_Key']}": {
                "product_onec_id": v["Номенклатура_Key"],
                "feature_onec_id": v["Характеристика_Key"],
                "price": v["Цена"],
            }
            for v in latest.values()
        }

    async def get_balances_1c(self, save: bool = False) -> dict[str, dict[str, Any]]:
        balances = await self.__fetch_odata(endpoints.BALANCES, save)
        return {
            f"{b['Номенклатура_Key']}_{b['Характеристика_Key']}": {
                "product_onec_id": b["Номенклатура_Key"],
                "feature_onec_id": b["Характеристика_Key"],
                "balance": b["Количество"],
            }
            for b in balances
        }

    async def get_features_1c(self, save: bool = False) -> dict[str, dict[str, Any]]:
        features_task = self.__fetch_odata(endpoints.FEATURES, save)
        prices_task = self.get_prices_1c(save)
        balances_task = self.get_balances_1c(save)

        features, prices_map, balances_map = await asyncio.gather(
            features_task, prices_task, balances_task
        )

        return {
            f.get("Ref_Key"): {
                "onec_id": f.get("Ref_Key"),
                "product_onec_id": f.get("Owner"),
                "name": f.get("Description"),
                "code": f.get("Code"),
                "file_id": f.get("ФайлКартинки_Key", None),
                "price": prices_map.get(f"{f.get('Owner')}_{f.get('Ref_Key')}", {}).get("price", "0"),
                "balance": balances_map.get(f"{f.get('Owner')}_{f.get('Ref_Key')}", {}).get("balance", "0"),
            }
            for f in features
            if f.get("DeletionMark") not in [True, "true"]
        }

    async def get_products_1c(self, save: bool = False) -> dict[str, dict[str, Any]]:
        products = await self.__fetch_odata(endpoints.PRODUCTS, save)
        return {
            p.get("Ref_Key"): {
                "onec_id": p.get("Ref_Key"),
                "category_onec_id": p.get("КатегорияНоменклатуры_Key"),
                "name": p.get("Description"),
                "code": p.get("Code"),
                "description": p.get("Комментарий"),
                "usage": next(
                    (
                        t.get("ТекстоваяСтрока", None)
                        for t in (p.get("ДополнительныеРеквизиты") or [])
                        if any(k in (t.get("ТекстоваяСтрока", "") or "") for k in keywords.use)
                    ),
                    None,
                ),
                "expiration": next(
                    (
                        t.get("ТекстоваяСтрока", None)
                        for t in (p.get("ДополнительныеРеквизиты") or [])
                        if any(k in (t.get("ТекстоваяСтрока", "") or "") for k in keywords.expire)
                    ),
                    None,
                ),
            }
            for p in products
            if p.get("КатегорияНоменклатуры_Key")
               and p.get("Недействителен") != "true"
               and p.get("DeletionMark") not in [True, "true"]
        }

    # --------------------------------------------------------------------------
    #                             DATABASE UPSERT
    # --------------------------------------------------------------------------

    async def _upsert_table(
            self,
            db,
            table,
            rows: list[dict[str, Any]],
            conflict_cols: list[str],
            update_cols: list[str],
    ) -> None:
        if not rows:
            return

        for i in range(0, len(rows), UPSERT_BATCH_SIZE):
            chunk = rows[i : i + UPSERT_BATCH_SIZE]
            stmt = pg_insert(table).values(chunk)
            stmt = stmt.on_conflict_do_update(
                index_elements=[getattr(table.c, c) for c in conflict_cols],
                set_={c: getattr(stmt.excluded, c) for c in update_cols},
            )
            await db.execute(stmt)

    async def update_db(self, approach: Literal["json", "postgres"], save: bool = False) -> None:
        products_task = self.get_products_1c(save)
        features_task = self.get_features_1c(save)
        categories_task = self.get_categories_1c(save)
        units_task = self.get_units_1c(save)

        products, features, categories, units = await asyncio.gather(
            products_task, features_task, categories_task, units_task
        )

        if approach != "postgres":
            self.log.info("🧾 Writing JSON export...")
            await asyncio.gather(
                self._write_json("products.json", products),
                self._write_json("features.json", features),
                self._write_json("categories.json", categories),
                self._write_json("units.json", units),
            )
            self.log.info("✅ JSON export completed.")
            return

        # IMPORTANT: adjust these imports if your models live elsewhere
        from src.webapp.models import Unit, Category, Product, Feature

        unit_rows = [
            {
                "onec_id": u["onec_id"],
                "name": u.get("name") or "",
                "description": u.get("description"),
            }
            for u in units.values()
            if u.get("onec_id")
        ]

        category_rows = [
            {
                "onec_id": c["onec_id"],
                "unit_onec_id": c.get("unit_onec_id"),
                "name": c.get("name") or "",
                "code": c.get("code"),
            }
            for c in categories.values()
            if c.get("onec_id")
        ]

        product_rows = [
            {
                "onec_id": p["onec_id"],
                "category_onec_id": p.get("category_onec_id"),
                "name": p.get("name") or "",
                "code": p.get("code"),
                "description": p.get("description"),
                "usage": p.get("usage"),
                "expiration": p.get("expiration"),
            }
            for p in products.values()
            if p.get("onec_id")
        ]

        feature_rows = [
            {
                "onec_id": f["onec_id"],
                "product_onec_id": f.get("product_onec_id"),
                "name": f.get("name") or "",
                "code": f.get("code"),
                "file_id": f.get("file_id"),
                "price": _dec(f.get("price")),
                "balance": _dec(f.get("balance")),
            }
            for f in features.values()
            if f.get("onec_id")
        ]

        self.log.info(
            f"🔁 UPSERT: units={len(unit_rows)} categories={len(category_rows)} "
            f"products={len(product_rows)} features={len(feature_rows)}"
        )

        # One DB session, one commit => stable + fast
        async with get_session() as db:
            # order matters if you have FKs
            await self._upsert_table(
                db,
                Unit.__table__,
                unit_rows,
                conflict_cols=["onec_id"],
                update_cols=["name", "description"],
            )

            await self._upsert_table(
                db,
                Category.__table__,
                category_rows,
                conflict_cols=["onec_id"],
                update_cols=["unit_onec_id", "name", "code"],
            )

            await self._upsert_table(
                db,
                Product.__table__,
                product_rows,
                conflict_cols=["onec_id"],
                update_cols=["category_onec_id", "name", "code", "description", "usage", "expiration"],
            )

            await self._upsert_table(
                db,
                Feature.__table__,
                feature_rows,
                conflict_cols=["onec_id"],
                update_cols=["product_onec_id", "name", "code", "file_id", "price", "balance"],
            )

            await db.commit()

    @staticmethod
    async def _write_json(file, data):
        async with aiofiles.open(file, "w", encoding="utf-8") as f:
            await f.write(json.dumps(data, ensure_ascii=False, indent=4))

    async def postgres_worker(self):
        while True:
            self.log.info("🔁 PostgreSQL upsert started...")
            try:
                await self.update_db("postgres", False)
                self.log.info("✅ PostgreSQL updated successfully (upsert).")
                await get_db_items(self.log)
            except Exception as e:
                self.log.exception(f"❌ Worker failed: {e}")
            await asyncio.sleep(SLEEP_INTERVAL)

    async def close(self):
        await self.__client.aclose()