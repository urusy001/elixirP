import asyncio
import json
import logging
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import List, Dict, Any, Literal

import aiofiles
import httpx

from config import ENTERPRISE_URL, ENTERPRISE_LOGIN, ENTERPRISE_PASSWORD
from src.onec import endpoints, keywords
from src.webapp import get_session
from src.webapp.crud import create_feature, create_unit, create_product, create_category
from src.webapp.database import get_db_items
from src.webapp.schemas import CategoryCreate, ProductCreate, UnitCreate, FeatureCreate


BATCH_SIZE = 50  # how many rows per commit
SLEEP_INTERVAL = 900  # seconds between syncs (15 min)


class OneCEnterprise:
    NS = {
        "m": "http://schemas.microsoft.com/ado/2007/08/dataservices/metadata",
        "d": "http://schemas.microsoft.com/ado/2007/08/dataservices",
        "atom": "http://www.w3.org/2005/Atom",
    }

    def __init__(self, url=ENTERPRISE_URL, username=ENTERPRISE_LOGIN, password=ENTERPRISE_PASSWORD):
        limits = httpx.Limits(max_connections=20, max_keepalive_connections=10)
        self.__client = httpx.AsyncClient(
            auth=(username, password), limits=limits, timeout=httpx.Timeout(30.0)
        )
        self.__url = url
        self.log = logging.getLogger(self.__class__.__name__)

    # --------------------------------------------------------------------------
    #                          FETCHING FROM 1C
    # --------------------------------------------------------------------------

    async def __fetch_odata(self, endpoint: str, save: bool = False) -> List[Dict[str, Any]]:
        """Fetch OData XML feed and parse <entry> records including ДополнительныеРеквизиты."""
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
            raise Exception(f"❌ Failed to fetch {url} after 3 attempts")

        root = ET.fromstring(response.content)
        entries: List[Dict[str, Any]] = []

        for entry in root.findall("atom:entry", self.NS):
            content = entry.find("atom:content/m:properties", self.NS)
            if content is None:
                continue

            record: Dict[str, Any] = {}
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
            async with aiofiles.open(f"{endpoint.split('?')[0]}.json", "w", encoding="utf-8") as f:
                await f.write(json.dumps(entries, ensure_ascii=False, indent=4))

        return entries

    async def get_units_1c(self, save: bool = False) -> Dict[str, Dict[str, Any]]:
        units = await self.__fetch_odata(endpoints.UNITS, save)
        return {
            u.get("Ref_Key"): {
                "onec_id": u.get("Ref_Key"),
                "name": u.get("Description"),
                "description": u.get("НаименованиеПолное"),
            }
            for u in units
        }

    async def get_categories_1c(self, save: bool = False) -> Dict[str, Dict[str, Any]]:
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
        }

    async def get_prices_1c(self, save: bool = False) -> Dict[str, Dict[str, Any]]:
        prices = await self.__fetch_odata(endpoints.PRICES, save)
        latest: Dict[tuple[str, str], Dict[str, Any]] = {}
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

    async def get_balances_1c(self, save: bool = False) -> Dict[str, Dict[str, Any]]:
        balances = await self.__fetch_odata(endpoints.BALANCES, save)
        return {
            f"{b['Номенклатура_Key']}_{b['Характеристика_Key']}": {
                "product_onec_id": b["Номенклатура_Key"],
                "feature_onec_id": b["Характеристика_Key"],
                "balance": b["Количество"],
            }
            for b in balances
        }

    async def get_features_1c(self, save: bool = False) -> Dict[str, Dict[str, Any]]:
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
        }

    async def get_products_1c(self, save: bool = False) -> Dict[str, Dict[str, Any]]:
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
                        for t in p.get("ДополнительныеРеквизиты", {})
                        if any(k in t.get("ТекстоваяСтрока", "") for k in keywords.use)
                    ),
                    None,
                ),
                "expiration": next(
                    (
                        t.get("ТекстоваяСтрока", None)
                        for t in p.get("ДополнительныеРеквизиты", {})
                        if any(k in t.get("ТекстоваяСтрока", "") for k in keywords.expire)
                    ),
                    None,
                ),
            }
            for p in products
            if p.get("КатегорияНоменклатуры_Key") and p.get("Недействителен") != "true"
        }

    # --------------------------------------------------------------------------
    #                             DATABASE SYNC
    # --------------------------------------------------------------------------

    async def batched_insert(self, create_func, schema_list, name: str):
        """Insert objects in small batches to prevent asyncpg disconnections."""
        if not schema_list:
            self.log.info(f"No {name} to insert.")
            return

        self.log.info(f"🟢 Inserting {len(schema_list)} {name}...")
        async def __task(obj):
            async with get_session() as db:
                await create_func(db, obj)


        for i in range(0, len(schema_list), BATCH_SIZE):
            batch = schema_list[i : i + BATCH_SIZE]
            try: await asyncio.gather(*[__task(obj) for obj in batch])
            except Exception as e: self.log.error(e)

        self.log.info(f"✅ Finished inserting {name}.")

    async def update_db(self, approach: Literal["json", "postgre"]) -> None:
        save = approach == "json"

        # --- 1️⃣ Fetch all data ---
        products_task = self.get_products_1c(save)
        features_task = self.get_features_1c(save)
        categories_task = self.get_categories_1c(save)
        units_task = self.get_units_1c(save)

        products, features, categories, units = await asyncio.gather(
            products_task, features_task, categories_task, units_task
        )

        # --- 2️⃣ Save ---
        if approach == "postgre":
            await self.batched_insert(create_unit, [UnitCreate(**u) for u in units.values()], "units")
            await self.batched_insert(create_category, [CategoryCreate(**c) for c in categories.values()], "categories")
            await self.batched_insert(create_product, [ProductCreate(**p) for p in products.values()], "products")
            await self.batched_insert(create_feature, [FeatureCreate(**f) for f in features.values()], "features")

        else:
            self.log.info("🧾 Writing JSON export...")
            await asyncio.gather(
                self._write_json("products.json", products),
                self._write_json("features.json", features),
                self._write_json("categories.json", categories),
                self._write_json("units.json", units),
            )
            self.log.info("✅ JSON export completed.")

    @staticmethod
    async def _write_json(file, data):
        async with aiofiles.open(file, "w", encoding="utf-8") as f:
            await f.write(json.dumps(data, ensure_ascii=False, indent=4))

    async def postgre_worker(self):
        """Periodic DB sync every 15 minutes."""
        while True:
            self.log.info("🔁 PostgreSQL sync started...")
            try:
                await self.update_db("postgre")
                self.log.info("✅ PostgreSQL DB updated successfully.")
                await get_db_items(self.log)
            except Exception as e:
                self.log.error(f"❌ Worker failed: {e}")
            await asyncio.sleep(SLEEP_INTERVAL)

    async def close(self):
        await self.__client.aclose()


# --------------------------------------------------------------------------
#                                   MAIN
# --------------------------------------------------------------------------
async def main():
    start = time.perf_counter()
    onec = OneCEnterprise()
    await onec.update_db("postgre")
    end = time.perf_counter()
    print(f"⏱ Initialization took {end - start:.2f} seconds")
    await onec.close()


if __name__ == "__main__":
    asyncio.run(main())