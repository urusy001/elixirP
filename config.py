from __future__ import annotations

import os
import logging
import pathlib

from datetime import timezone, timedelta
from urllib.parse import quote_plus
from dotenv import load_dotenv
from starlette.templating import Jinja2Templates

def env(name: str, default: str | None = None, *, strip: bool = True) -> str | None:
    v = os.getenv(name, default)
    if v is None:
        return None
    return v.strip() if strip else v
def env_int(name: str, default: int | None = None) -> int | None:
    v = env(name)
    if v is None or v == "":
        return default
    try:
        return int(v)
    except ValueError:
        return default
def env_list_ints(name: str) -> list[int]:
    raw = env(name, "")
    if not raw:
        return []
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    out: list[int] = []
    for p in parts:
        try:
            out.append(int(p))
        except ValueError:
            pass
    return out

def build_sync_dsn(user: str, password: str, host: str, port: int, db: str) -> str:
    return (
        f"postgresql+psycopg2://{quote_plus(user)}:{quote_plus(password)}"
        f"@{host}:{port}/{quote_plus(db)}"
    )
def build_async_dsn(user: str, password: str, host: str, port: int, db: str) -> str:
    return (
        f"postgresql+asyncpg://{quote_plus(user)}:{quote_plus(password)}"
        f"@{host}:{port}/{quote_plus(db)}"
    )

load_dotenv()

MOSCOW_TZ = timezone(timedelta(hours=3))

OWNER_TG_IDS      = env_list_ints("OWNER_TG_IDS")
TELETHON_API_ID   = env("TELETHON_API_ID", "")
TELETHON_API_HASH = env("TELETHON_API_HASH", "")
TELETHON_PHONE    = env("TELETHON_PHONE", "")
TELETHON_PASSWORD = env("TELETHON_PASSWORD", None)

ADMIN_PANEL_TOKEN = env("ADMIN_PANEL_TOKEN", "")
ELIXIR_CHAT_ID = env_int("ELIXIR_CHAT_ID", 0)

PROFESSOR_BOT_TOKEN  = env("PROFESSOR_BOT_TOKEN", "")
DOSE_BOT_TOKEN = env("DOSE_BOT_TOKEN", "")
NEW_BOT_TOKEN = env("NEW_BOT_TOKEN", "")

PROFESSOR_ASSISTANT_ID  = env("PROFESSOR_ASSISTANT_ID", "")
DOSE_ASSISTANT_ID = env("DOSE_ASSISTANT_ID", "")
NEW_ASSISTANT_ID = env("NEW_ASSISTANT_ID", "")

PROFESSOR_OPENAI_API  = env("PROFESSOR_OPENAI_API", "")
DOSE_OPENAI_API = env("DOSE_OPENAI_API", "")
NEW_OPENAI_API = env("NEW_OPENAI_API", "")

POSTGRES_USER     = env("POSTGRES_USER", "postgres") or "postgres"
POSTGRES_PASSWORD = env("POSTGRES_PASSWORD", "") or ""
POSTGRES_DB       = env("POSTGRES_DB", "postgres") or "postgres"
POSTGRES_HOST     = env("POSTGRES_HOST", "localhost") or "localhost"
POSTGRES_PORT     = env_int("POSTGRES_PORT", 5432) or 5432

SYNC_DATABASE_URL  = build_sync_dsn(POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB)
ASYNC_DATABASE_URL = build_async_dsn(POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB)

BASE_DIR = pathlib.Path(__file__).resolve().parent
WORKING_DIR = BASE_DIR

SPA_DIR = BASE_DIR / "src" / "webapp" / "static"
SRC_DIR       = BASE_DIR / "src"
IMAGES_DIR    = SRC_DIR / "webapp" / "static" / "images"
DATA_DIR      = BASE_DIR / "data"
LOGS_DIR      = BASE_DIR / "logs"
DOWNLOADS_DIR = DATA_DIR / "downloads"
GIVEAWAYS_DIR = DATA_DIR / "giveaways"
SPENDS_DIR    = DATA_DIR / "spends"
TEMPLATES_DIR = BASE_DIR / "src" / "webapp" / "templates"

for d in (DATA_DIR, DOWNLOADS_DIR, GIVEAWAYS_DIR, SPENDS_DIR): d.mkdir(parents=True, exist_ok=True)
templates = Jinja2Templates(directory=TEMPLATES_DIR)

ENTERPRISE_LOGIN    = env("ENTERPRISE_LOGIN", "")
ENTERPRISE_PASSWORD = env("ENTERPRISE_PASSWORD", "")
ENTERPRISE_URL      = env("ENTERPRISE_URL", "")

CDEK_ACCOUNT         = env("CDEK_ACCOUNT", "")
CDEK_SECURE_PASSWORD = env("CDEK_SECURE_PASSWORD", "")
CDEK_API_URL         = env("CDEK_API_URL", "")

CDEK_SENDER_CITY_CODE    = 256
CDEK_SENDER_POSTAL_CODE  = "450078"
CDEK_SENDER_COUNTRY_CODE = "RU"
CDEK_SENDER_CITY         = "Уфа"
CDEK_SENDER_ADDRESS      = "ул. Революционная, 98/1 блок А"

CDEK_SENDER_NAME  = "ИП Хоменко Татьяна Ивановна"
CDEK_SENDER_PHONE = "+79610387977"
CDEK_SENDER_EMAIL = "shop@example.com"

YANDEX_DELIVERY_BASE_URL          = env("YANDEX_DELIVERY_BASE_URL", "")
YANDEX_DELIVERY_WAREHOUSE_ID      = env("YANDEX_DELIVERY_WAREHOUSE_ID", "")
YANDEX_MAP_TOKEN                  = env("YANDEX_MAP_TOKEN", "")
YANDEX_GEOCODER_TOKEN             = env("YANDEX_GEOCODER_TOKEN", "")
YANDEX_DELIVERY_TOKEN             = env("YANDEX_DELIVERY_TOKEN", "")
YANDEX_WAREHOUSE_ADDRESS_FULLNAME = "ул. Революционная, 80, Уфа, Респ. Башкортостан, Россия"
YANDEX_WAREHOUSE_LON              = 55.9744433695682
YANDEX_WAREHOUSE_LAT              = 54.73178065859432

YOOKASSA_SECRET_KEY = env("YOOKASSA_SECRET_KEY", "")
YOOKASSA_SHOP_ID    = env("YOOKASSA_SHOP_ID", "")
YOOKASSA_API_URL    = env("YOOKASSA_API_URL", "")

AMOCRM_CLIENT_SECRET  = env("AMOCRM_CLIENT_SECRET", "")
AMOCRM_CLIENT_ID      = env("AMOCRM_CLIENT_ID", "")
AMOCRM_LONG_TOKEN     = env("AMOCRM_LONG_TOKEN", "")
AMOCRM_AUTH_CODE      = env("AMOCRM_AUTH_CODE", "")
AMOCRM_REDIRECT_URI   = env("AMOCRM_REDIRECT_URI", "")
AMOCRM_BASE_DOMAIN    = env("AMOCRM_BASE_DOMAIN", "")
AMOCRM_ACCESS_TOKEN   = env("AMOCRM_ACCESS_TOKEN", "")
AMOCRM_REFRESH_TOKEN  = env("AMOCRM_REFRESH_TOKEN", "")
AMOCRM_LOGIN_EMAIL    = env("AMOCRM_LOGIN_EMAIL", "")
AMOCRM_LOGIN_PASSWORD = env("AMOCRM_LOGIN_PASSWORD", "")


_log = logging.getLogger("config")
if not OWNER_TG_IDS: _log.warning("ADMIN_TG_IDS is empty or invalid; admin-only filters may not work.")
if not PROFESSOR_BOT_TOKEN: _log.warning("AI_BOT_TOKEN is empty.")

BOT_NAMES = {
    PROFESSOR_BOT_TOKEN: "@ProfessorOfPeptidesbot",
    DOSE_BOT_TOKEN: "@Peptideexpertbot",
    NEW_BOT_TOKEN: "@peptidestestbot",
}

BOT_KEYWORDS = {
    PROFESSOR_ASSISTANT_ID: "professor",
    DOSE_ASSISTANT_ID: "dose",
    NEW_ASSISTANT_ID: "new",
}

API_PREFIX = "/api/v1"