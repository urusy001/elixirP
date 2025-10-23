import json
import logging
import asyncio
import httpx
from datetime import datetime, timedelta, UTC

from config import AMOCRM_CLIENT_ID, AMOCRM_CLIENT_SECRET, AMOCRM_REDIRECT_URI, AMOCRM_BASE_DOMAIN, \
    AMOCRM_REFRESH_TOKEN, AMOCRM_ACCESS_TOKEN, AMOCRM_AUTH_CODE


class AsyncAmoCRM:
    def __init__(
        self,
        base_domain: str,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        access_token: str | None = None,
        refresh_token: str | None = None,
    ):
        self.COMPLETE_STATUS_IDS = [75784946, 75784942, 76566302, 76566306, 142]
        self.PIPELINE_ID = 9280278
        self.logger = logging.getLogger(self.__class__.__name__)
        self.base_domain = base_domain
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.expires_at = datetime.now(UTC) + timedelta(days=1)

    # ---------- 1️⃣ Token Management ----------

    async def __request_token(self, grant_type: str, code: str | None = None):
        url = f"https://{self.base_domain}/oauth2/access_token"
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
            "grant_type": grant_type,
        }

        if grant_type == "authorization_code":
            payload["code"] = code
        elif grant_type == "refresh_token":
            payload["refresh_token"] = self.refresh_token
        print(payload)

        async with httpx.AsyncClient() as client:
            res = await client.post(url, json=payload)
            print(res.text)
            res.raise_for_status()
            data = res.json()

        self.access_token = data["access_token"]
        self.refresh_token = data["refresh_token"]
        self.expires_at = datetime.now(UTC) + timedelta(seconds=data["expires_in"])
        return data

    async def _request(self, method: str, endpoint: str, **kwargs):
        await self.ensure_token_valid()
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self.access_token}"
        url = f"https://{self.base_domain}{endpoint}"

        async with httpx.AsyncClient() as client:
            res = await client.request(method, url, headers=headers, **kwargs)

            # Если токен истёк — пробуем обновить и повторить запрос
            if res.status_code == 401:
                self.logger.warning("Access token expired, refreshing...")
                await self.refresh()
                headers["Authorization"] = f"Bearer {self.access_token}"
                res = await client.request(method, url, headers=headers, **kwargs)

            res.raise_for_status()
            if res.text.strip():
                return res.json()
            return {}

    async def authorize(self, code: str):
        """Exchange initial authorization code for tokens."""
        return await self.__request_token("authorization_code", code)

    async def refresh(self):
        """Refresh the access token when expired."""
        return await self.__request_token("refresh_token")

    async def ensure_token_valid(self):
        """Automatically refresh token if expired."""
        if not self.access_token or datetime.now(UTC) >= self.expires_at:
            await self.refresh()

    async def get(self, endpoint: str, **kwargs):
        return await self._request("GET", endpoint, **kwargs)

    async def post(self, endpoint: str, **kwargs):
        return await self._request("POST", endpoint, **kwargs)

    async def patch(self, endpoint: str, **kwargs):
        return await self._request("PATCH", endpoint, **kwargs)

    async def delete(self, endpoint: str, **kwargs):
        return await self._request("DELETE", endpoint, **kwargs)

    async def get_valid_deal(self, code: str | int,  start_date: datetime):
        code_str = str(code).strip()
        endpoint = f"/api/v4/leads?query=№{code_str}"
        data = await self.get(endpoint)
        print('data', data)

        leads = data.get("_embedded", {}).get("leads", [])

        for lead in leads:
            name = lead.get("name", "").strip()
            normalized = name.lower().replace(" ", " ").replace("\u00a0", " ")
            pipeline_id = lead.get("pipeline_id", 0)
            status_id = lead.get("status_id", 0)
            if normalized.startswith(f"заказ №{code_str}") and (
                " " not in normalized[len(f"заказ №{code_str}"):]  # next char isn't digit
                or normalized[len(f"заказ №{code_str}"):] in ("", " с сайта elixirpeptide")
            ) and pipeline_id == self.PIPELINE_ID and status_id in self.COMPLETE_STATUS_IDS:
                self.logger.info(f"Found lead: {name}")
                timestamp = lead.get('closed_at', None) or lead.get('updated_at', None)
                date = datetime.fromtimestamp(timestamp, UTC)
                if lead.get("created_at") < start_date.timestamp():
                    print(datetime.fromtimestamp(lead.get("created_at")), datetime.fromtimestamp(start_date.timestamp()))
                    self.logger.info(f"Lead {name} has expired, {lead.get('created_at')}.")
                    return False, 'Заказ должен быть совершен после даты начала розыгрыша'
                return True, date

        self.logger.warning(f"No done lead with code: {code_str}")
        return False, "Заказ не найден по коду " + code_str

amocrm = AsyncAmoCRM(
    base_domain=AMOCRM_BASE_DOMAIN,
    client_id=AMOCRM_CLIENT_ID,
    client_secret=AMOCRM_CLIENT_SECRET,
    redirect_uri=AMOCRM_REDIRECT_URI,
    access_token=AMOCRM_ACCESS_TOKEN,
    refresh_token=AMOCRM_REFRESH_TOKEN,
)

async def save_leads_json():
    # Example: get all leads updated this week
    now = datetime.now(UTC)
    start_of_week = (now - timedelta(days=now.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    t_from = int(start_of_week.timestamp())
    t_to = int(now.timestamp())

    params = {
        "filter[updated_at][from]": t_from,
        "filter[updated_at][to]": t_to,
    }

    # Just get the raw JSON result
    data = await amocrm.get("/api/v4/leads", params=params)

    # Save it to a file
    with open("leads_raw.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("✅ Saved response to leads_raw.json")

if __name__ == "__main__":
    asyncio.run(save_leads_json())
