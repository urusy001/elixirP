import json
import logging

import httpx
from fastapi import APIRouter, Request, Query
from fastapi.responses import Response

from config import CDEK_API_URL, YANDEX_GEOCODER_TOKEN
from src.delivery.sdek import client as cdek_client

logger = logging.getLogger(__name__)

cdek_router = APIRouter(prefix="/delivery/cdek", tags=["cdek"])
yandex_router = APIRouter(prefix="/delivery/yandex", tags=["yandex"])


@cdek_router.api_route(path="", methods=["GET", "POST"])
async def cdek_proxy(request: Request):
    headers = {"Authorization": f"Bearer {cdek_client._access_token}"}

    params = request.query_params
    raw_body = await request.body()
    try:
        body = json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError:
        body = {}
    method = request.method

    action = params.get("action") or body.get("action")
    if action == "offices":
        endpoint = f"{CDEK_API_URL}/deliverypoints"
    elif action == "calculate":
        if isinstance(body, dict):
            to_location = body.get("to_location", None)
            if to_location and isinstance(to_location, dict):
                endpoint = f"{CDEK_API_URL}/calculator/tarifflist"
            else:
                return Response(status_code=400, content='{"error": "Invalid to_location"}')
        else:
            return Response(status_code=400, content='{"error": "Invalid body"}')
    else:
        return Response(status_code=400, content='{"error": "Unknown action"}')

    async with httpx.AsyncClient() as client:
        if method == "GET":
            resp = await client.get(endpoint, params=params, headers=headers)
        else:
            resp = await client.post(
                endpoint,
                content=raw_body,
                headers={**headers, "Content-Type": "application/json"},
            )

    with open(f'{action}.json', 'w', encoding="utf-8") as f:
        json.dump(json.loads(resp.text), f, ensure_ascii=False, indent=4)

    if action == "calculate" and resp.status_code == 200:
        try:
            data = resp.json()

            # "tariff_codes" contains list of tariff options
            tariffs = data.get("tariff_codes", [])
            filtered = [
                t for t in tariffs
                if isinstance(t, dict)
                   and t.get("tariff_name", "").lower().find("склад-") != -1
            ]

            data["tariff_codes"] = filtered
            print(f"🟢 Filtered {len(filtered)} tariffs (дверь → ...)")

            return Response(
                content=json.dumps(data, ensure_ascii=False),
                status_code=200,
                media_type="application/json",
            )
        except Exception as e:
            print("⚠️ Error filtering tariffs:", e)

    # --- fallback: return raw response ---
    return Response(
        content=resp.content,
        status_code=resp.status_code,
        media_type="application/json",
    )


@yandex_router.get("/reverse-geocode")
async def reverse_geocode(lat: float = Query(...), lon: float = Query(...)):
    url = "https://geocode-maps.yandex.ru/1.x/"
    params = {"apikey": YANDEX_GEOCODER_TOKEN, "geocode": f"{lon},{lat}", "format": "json"}
    async with httpx.AsyncClient() as client:
        r = await client.get(url, params=params)
        data = r.json()
    try:
        components = (
            data["response"]["GeoObjectCollection"]["featureMember"][0]["GeoObject"]
            ["metaDataProperty"]["GeocoderMetaData"]["Address"]["Components"]
        )
        city = next((c["name"] for c in components if c["kind"] == "locality"), None)
    except Exception:
        city = None
    logger.info(str({"city": city or "Москва"}))
    return {"city": city or "Москва"}
