import json
import requests

from config import YANDEX_DELIVERY_TOKEN, YANDEX_WAREHOUSE_LAT, YANDEX_WAREHOUSE_LON


def test_yandex_offers_calculate(
        oauth_token: str,
        src_lon: float,
        src_lat: float,
        src_fullname: str,
        dst_lon: float,
        dst_lat: float,
        dst_fullname: str,
        length_m: float = 0.25,
        width_m: float = 0.15,
        height_m: float = 0.10,
        weight_kg: float = 0.10,
        quantity: int = 1,
        lang: str = "ru",
        base_url: str = "https://b2b.taxi.yandex.net",
) -> dict:
    url = f"{base_url}/b2b/cargo/integration/v2/offers/calculate"

    headers = {
        "Authorization": f"Bearer {oauth_token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Accept-Language": lang,
    }

    body = {
        "items": [
            {
                "size": {"length": length_m, "width": width_m, "height": height_m},
                "weight": weight_kg,
                "quantity": quantity,
                "pickup_point": 1,
                "dropoff_point": 2,
            }
        ],
        "route_points": [
            {
                "id": 1,
                "coordinates": [src_lon, src_lat],  # IMPORTANT: [lon, lat]
                "fullname": src_fullname,
            },
            {
                "id": 2,
                "coordinates": [dst_lon, dst_lat],  # IMPORTANT: [lon, lat]
                "fullname": dst_fullname,
            },
        ],
        "requirements": {
            "taxi_classes": ["express"]
        },
    }

    resp = requests.post(url, headers=headers, json=body, timeout=20)
    if not resp.ok:
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text}")

    return resp.json()


if __name__ == "__main__":
    token = YANDEX_DELIVERY_TOKEN

    data = test_yandex_offers_calculate(
        oauth_token=token,
        src_lon=YANDEX_WAREHOUSE_LAT,
        src_lat=YANDEX_WAREHOUSE_LON,
        src_fullname="ул. Революционная, 80, Уфа, Респ. Башкортостан, Россия",
        dst_lon=56.12276822021486,
        dst_lat=54.78583031190476,
        dst_fullname="Республика Башкортостан, Уфа, бульвар Тухвата Янаби, 38",
        lang="ru",
    )

    print(json.dumps(data, indent=4, ensure_ascii=False))