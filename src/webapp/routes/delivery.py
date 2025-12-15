import json
import logging
import httpx
from fastapi import APIRouter, Request, Query, HTTPException
from fastapi.responses import Response

from config import CDEK_API_URL, YANDEX_GEOCODER_TOKEN, YANDEX_DELIVERY_TOKEN, YANDEX_DELIVERY_BASE_URL
from src.delivery.sdek import client as cdek_client

logger = logging.getLogger(__name__)

cdek_router = APIRouter(prefix="/delivery/cdek", tags=["cdek"])
yandex_router = APIRouter(prefix="/delivery/yandex", tags=["yandex"])


@cdek_router.api_route(path="", methods=["GET", "POST"])
async def cdek_proxy(request: Request):
    headers = {"Authorization": f"Bearer {cdek_client._access_token}"}

    params = request.query_params
    raw_body = await request.body()
    raw_body = raw_body.decode(encoding="utf-8")
    body = json.loads(raw_body) if raw_body else {}
    method = request.method

    action = params.get("action") or body.get("action")
    if action == "offices": endpoint = f"{CDEK_API_URL}/deliverypoints"
    elif action == "calculate":
        if isinstance(body, dict) and isinstance(body.get("to_location"), dict):
            print(body.get("to_location"), body.get("from_location"))
            endpoint = f"{CDEK_API_URL}/calculator/tarifflist"
            body.update({"type": 2})
        else: return Response(status_code=400, content='{"error":"Invalid to_location"}')
    else: return Response(status_code=400, content='{"error":"Unknown action"}')

    timeout = httpx.Timeout(connect=5, read=15, write=10, pool=5)
    async with httpx.AsyncClient(timeout=timeout) as client:
        if method == "GET": resp = await client.get(endpoint, params=params, headers=headers)
        else: resp = await client.post(endpoint, content=raw_body, headers={**headers, "Content-Type": "application/json"})


    if action == "calculate" and resp.status_code == 200:
        try:
            data = resp.json()
            tariffs = data.get("tariff_codes", [])
            filtered = [
                t for t in tariffs
                if isinstance(t, dict) and "tariff_name" in t
                   and (t.get("tariff_name", "").lower().find("склад-склад") != -1) or (t.get("tariff_name", "").lower().find("склад-дверь") != -1)
            ]
            data["tariff_codes"] = filtered
            return Response(
                content=json.dumps(data, ensure_ascii=False),
                status_code=200,
                media_type="application/json",
            )
        except Exception as e:
            logger.warning("Error filtering tariffs: %s", e)

    return Response(content=resp.content, status_code=resp.status_code, media_type="application/json")

@yandex_router.get("/reverse-geocode")
async def reverse_geocode(
        lat: float = Query(...),
        lon: float = Query(...)
):
    """
    1) Yandex Geocoder 1.x -> extract city name from coords
    2) Yandex B2B /location/detect -> return up to 2 variants as
       [{'geo_id': <int>, 'address': <str>}, ...]

    Response:
    {
      "city": "<resolved city name or 'Москва'>",
      "variants": [{"geo_id": 213, "address": "Москва"}, ...]  # max 2
    }
    """
    if not YANDEX_GEOCODER_TOKEN: raise HTTPException(status_code=512, detail='YANDEX TOKEN NOT CONFIGURED')

    # --- 1) Reverse geocode coords -> city name ---
    geo_url = "https://geocode-maps.yandex.ru/1.x/"
    geo_params = {
        "apikey": YANDEX_GEOCODER_TOKEN,
        "geocode": f"{lon},{lat}",
        "format": "json",
        "lang": "ru_RU",
        "results": 5,
    }
    timeout = httpx.Timeout(connect=5, read=15, write=10, pool=5)
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.get(geo_url, params=geo_params)
        r.raise_for_status()
        data = r.json()

    try:
        members = data["response"]["GeoObjectCollection"]["featureMember"]
        first = members[0]["GeoObject"]
        address = first["metaDataProperty"]["GeocoderMetaData"]["Address"]
        comps = address["Components"]
        country_code = address["country_code"]
        formatted = address["formatted"]
        city_name = next((c["name"] for c in comps if c.get("kind") == "locality"), None) or "Москва"
    except Exception:
        city_name = "Москва"
        country_code = 'RU'
        formatted = "Улица Пушкина, дом Колотушина"

    if not YANDEX_DELIVERY_TOKEN: return {"city": city_name, "variants": []}

    # --- 2) /location/detect -> variants [{'geo_id': int, 'address': str}] ---
    detect_url = f"{YANDEX_DELIVERY_BASE_URL}/api/b2b/platform/location/detect"
    headers = {
        "Authorization": f"Bearer {YANDEX_DELIVERY_TOKEN}",
        "Content-Type": "application/json",
        "Accept-Language": "ru/ru",
    }
    payload = {"location": city_name}

    variants_out = []
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            resp = await client.post(detect_url, json=payload, headers=headers)
            resp.raise_for_status()
            ddata = resp.json()
            raw = ddata.get("variants") or []
            for v in raw:
                geo_id = v.get("geo_id")
                address = v.get("address") or ""
                if geo_id is None: continue
                variants_out.append({"geo_id": int(geo_id), "address": address})
        except Exception as e:
            logger.warning("location/detect failed for %s: %s", city_name, e)
            variants_out = []

    return {"city": city_name, "country_code": country_code, "formatted": formatted, "variants": variants_out}

@yandex_router.post("/get-pvz")
async def get_pvz(req: dict):
    """
    Unified Yandex PVZ fetcher.

    Accepts either:
    • geo_id — exact city;
    • latitude/longitude as intervals (each with 'from'/'to');
    • latitude + longitude + radius (meters) — fallback.
    """

    if not YANDEX_DELIVERY_TOKEN: raise HTTPException(500, "Yandex Delivery token not configured")
    payload = {
        "type": "pickup_point",
        "is_yandex_branded": True,
        "is_post_office": True,
        "is_not_branded_partner_station": True,
        "payment_methods": ["already_paid", "card_on_receipt"],
    }
    if "geo_id" in req and req["geo_id"] is not None: payload["geo_id"] = int(req["geo_id"])

    # Priority 2: intervals
    elif (
            isinstance(req.get("latitude"), dict)
            and isinstance(req.get("longitude"), dict)
            and "from" in req["latitude"]
            and "from" in req["longitude"]
    ):
        payload["latitude"] = req["latitude"]
        payload["longitude"] = req["longitude"]

    # Priority 3: simple coords + radius → convert to intervals
    elif "latitude" in req and "longitude" in req:
        lat = float(req["latitude"])
        lon = float(req["longitude"])
        radius = int(req.get("radius", 10000))
        radius = max(100, min(40000, radius))  # clamp 100–40000 m

        # convert meters → degrees (approx)
        km = radius / 1000
        dlat = km / 111.0
        dlon = km / (111.32 * max(0.1, abs(__import__("math").cos(lat * 3.1416 / 180))))

        payload["latitude"] = {"from": lat - dlat, "to": lat + dlat}
        payload["longitude"] = {"from": lon - dlon, "to": lon + dlon}

    else: raise HTTPException(400, "Provide geo_id or latitude/longitude (+optional radius)")

    # ---------------- Send to Yandex ---------------- #
    headers = {
        "Authorization": f"Bearer {YANDEX_DELIVERY_TOKEN}",
        "Content-Type": "application/json",
    }
    url = f"{YANDEX_DELIVERY_BASE_URL}/api/b2b/platform/pickup-points/list"

    timeout = httpx.Timeout(connect=5, read=20, write=10, pool=5)
    async with httpx.AsyncClient(timeout=timeout) as client: resp = await client.post(url, json=payload, headers=headers)
    if resp.status_code != 200: raise HTTPException(status_code=resp.status_code, detail=resp.text)
    logger.info("pickup payload: %s", json.dumps(payload, ensure_ascii=False))
    return resp.json()

@yandex_router.get("/get-pvz-all")
async def get_all_pvz():
    """
    Load all PVZ for Russia + Kazakhstan (merged cache or direct Yandex call).
    This endpoint should respond with:
        { "points": [ ... ] }
    """
    if not YANDEX_DELIVERY_TOKEN: raise HTTPException(500, "Token missing")

    payload = {
        "type": "pickup_point",
        "country_codes": ["RU", "KZ"],
        "is_yandex_branded": True,
        "is_post_office": True,
        "is_not_branded_partner_station": True,
        "payment_methods": ["already_paid", "card_on_receipt"],
    }

    headers = {
        "Authorization": f"Bearer {YANDEX_DELIVERY_TOKEN}",
        "Content-Type": "application/json",
    }
    url = f"{YANDEX_DELIVERY_BASE_URL}/api/b2b/platform/pickup-points/list"

    async with httpx.AsyncClient(timeout=60) as client: resp = await client.post(url, json=payload, headers=headers)
    if resp.status_code != 200: raise HTTPException(resp.status_code, resp.text)
    return resp.json()
