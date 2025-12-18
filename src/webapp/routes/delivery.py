import json
import logging
from typing import Any, Optional

import httpx
from fastapi import APIRouter, Request, Query, HTTPException
from fastapi.responses import Response

from config import CDEK_API_URL, YANDEX_GEOCODER_TOKEN, YANDEX_DELIVERY_TOKEN, YANDEX_DELIVERY_BASE_URL, \
    YANDEX_DELIVERY_WAREHOUSE_ID
from src.delivery.sdek import client as cdek_client
from src.webapp.schemas.yadev import PickupPointsResponse, CalcRequest

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


@yandex_router.get("/get-pvz-all", response_model=PickupPointsResponse)
async def get_pvz_all(
        geo_id: Optional[int] = Query(default=None),
        lat_from: Optional[float] = Query(default=None),
        lat_to: Optional[float] = Query(default=None),
        lon_from: Optional[float] = Query(default=None),
        lon_to: Optional[float] = Query(default=None),
):
    if not YANDEX_DELIVERY_TOKEN: raise HTTPException(status_code=500, detail="YANDEX_DELIVERY_TOKEN is not set")

    url = f"{YANDEX_DELIVERY_BASE_URL}/api/b2b/platform/pickup-points/list"
    headers = {
        "Authorization": f"Bearer {YANDEX_DELIVERY_TOKEN}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Accept-Language": "ru",
    }

    common_body: dict[str, Any] = {}
    if geo_id is not None: common_body["geo_id"] = geo_id
    if lat_from is not None and lat_to is not None: common_body["latitude"] = {"from": lat_from, "to": lat_to}
    if lon_from is not None and lon_to is not None: common_body["longitude"] = {"from": lon_from, "to": lon_to}

    async with httpx.AsyncClient(timeout=20.0) as client:
        points: list[dict[str, Any]] = []
        seen: set[str] = set()

        for t in ("pickup_point", "terminal"):
            body = {**common_body, "type": t}
            r = await client.post(url, headers=headers, json=body)
            if r.status_code >= 400: raise HTTPException(status_code=502, detail=f"Yandex pickup-points/list error: {r.text}")
            data = r.json()
            for p in (data.get("points") or []):
                pid = str(p.get("id") or p.get("ID") or "")
                key = pid if pid else f'{t}:{p.get("operator_station_id")}'
                if key in seen: continue
                seen.add(key)


                p_out = {
                    "id": pid or p.get("ID"),  # ВАЖНО: это то, что пойдёт в destination.platform_station_id
                    "type": p.get("type") or t,
                    "name": p.get("name"),
                    "position": p.get("position"),
                    "address": p.get("address"),
                    "contact": p.get("contact"),
                    "schedule": p.get("schedule"),
                    "dayoffs": p.get("dayoffs"),
                    "payment_methods": p.get("payment_methods"),
                    "operator_station_id": p.get("operator_station_id"),
                }
                points.append(p_out)

    return {"points": points}


@yandex_router.post("/calculate")
async def yandex_calculate(req: CalcRequest):
    if not YANDEX_DELIVERY_TOKEN: raise HTTPException(status_code=500, detail="YANDEX_DELIVERY_TOKEN is not set")
    if not YANDEX_DELIVERY_WAREHOUSE_ID: raise HTTPException(status_code=500, detail="YANDEX_SOURCE_PLATFORM_STATION_ID is not set")
    if req.delivery_mode == "self_pickup" and not req.destination.platform_station_id: raise HTTPException(status_code=400, detail="destination.platform_station_id is required for self_pickup")
    if req.delivery_mode == "time_interval" and not req.destination.address: raise HTTPException(status_code=400, detail="destination.address is required for time_interval")

    headers = {
        "Authorization": f"Bearer {YANDEX_DELIVERY_TOKEN}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Accept-Language": "ru",
    }

    pricing_url = f"{YANDEX_DELIVERY_BASE_URL}/api/b2b/platform/pricing-calculator"
    offers_info_url = f"{YANDEX_DELIVERY_BASE_URL}/api/b2b/platform/offers/info"

    pricing_body: dict[str, Any] = {
        "source": {"platform_station_id": YANDEX_DELIVERY_WAREHOUSE_ID},
        "destination": (
            {"platform_station_id": req.destination.platform_station_id}
            if req.delivery_mode == "self_pickup"
            else {"address": req.destination.address}
        ),
        "tariff": req.delivery_mode,
        "total_weight": req.total_weight,
        "total_assessed_price": req.total_assessed_price,
        "client_price": req.client_price,
        "payment_method": req.payment_method,
        "places": [p.model_dump() for p in req.places],
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        pr = await client.post(
            pricing_url,
            headers=headers,
            params={"is_oversized": str(req.is_oversized).lower()},
            json=pricing_body,
        )
        if pr.status_code >= 400: raise HTTPException(status_code=502, detail=f"Yandex pricing-calculator error: {pr.text}")

        pricing = pr.json()
        pricing_total = pricing.get("pricing_total")
        delivery_days = pricing.get("delivery_days")

        params: dict[str, Any] = {
            "station_id": YANDEX_DELIVERY_WAREHOUSE_ID,
            "last_mile_policy": req.delivery_mode,
            "send_unix": str(req.send_unix).lower(),
        }
        if req.delivery_mode == "self_pickup": params["self_pickup_id"] = req.destination.platform_station_id
        else: params["full_address"] = req.destination.address

        oi = await client.get(offers_info_url, headers=headers, params=params)

        best_interval = None
        offers_count = 0
        if oi.status_code == 200:
            offers_info = oi.json()
            offers = offers_info.get("offers") or []
            offers_count = len(offers)
            if offers: best_interval = min(offers, key=lambda x: x.get("from", 10**18))
        else:
            offers_info = {"status_code": oi.status_code, "body": oi.text}

    return {
        "ok": True,
        "delivery_mode": req.delivery_mode,
        "price": {"pricing_total": pricing_total, "currency": "RUB"},
        "delivery_days": delivery_days,
        "best_interval": best_interval,
        "offers_count": offers_count,
        "offers_info": offers_info,   
    }