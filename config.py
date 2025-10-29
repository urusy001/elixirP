import os
import pathlib
from datetime import timezone, timedelta

from dotenv import load_dotenv
from starlette.templating import Jinja2Templates


load_dotenv()
MOSCOW_TZ = timezone(timedelta(hours=3))
ADMIN_TG_IDS = [int(i) for i in os.getenv("ADMIN_TG_IDS").split(",")]

AI_BOT_TOKEN = os.getenv("AI_BOT_TOKEN")
AI_BOT_TOKEN2 = os.getenv("AI_BOT_TOKEN2")
AI_BOT_TOKEN3 = os.getenv("AI_BOT_TOKEN3")
ASSISTANT_ID3 = os.getenv("ASSISTANT_ID3")
OPENAI_API_KEY2 = os.getenv("OPENAI_API_KEY2")
ASSISTANT_ID = os.getenv("ASSISTANT_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ASSISTANT_ID2 = os.getenv("ASSISTANT_ID2")

POSTGRES_USER = os.getenv("POSTGRES_USER")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
POSTGRES_DB = os.getenv("POSTGRES_DB")
POSTGRES_HOST = os.getenv("POSTGRES_HOST")
POSTGRES_PORT = os.getenv("POSTGRES_PORT")
SYNC_DATABASE_URL = f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
ASYNC_DATABASE_URL = f"postgresql+asyncpg://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"

WORKING_DIR = BASE_DIR = pathlib.Path(__file__).resolve().parent
DATA_DIR = os.path.join(WORKING_DIR, "data")
DOWNLOADS_DIR = os.path.join(DATA_DIR, "downloads")
GIVEAWAYS_DIR = os.path.join(DATA_DIR, "giveaways")
SPENDS_DIR = os.path.join(DATA_DIR, "spends")
templates = Jinja2Templates(directory=BASE_DIR / "src" / "webapp" / "templates")

ENTERPRISE_LOGIN = os.getenv("ENTERPRISE_LOGIN")
ENTERPRISE_PASSWORD = os.getenv("ENTERPRISE_PASSWORD")
ENTERPRISE_URL = os.getenv("ENTERPRISE_URL")

CDEK_ACCOUNT = os.getenv("CDEK_ACCOUNT")
CDEK_SECURE_PASSWORD = os.getenv("CDEK_SECURE_PASSWORD")
CDEK_API_URL = os.getenv("CDEK_API_URL")

YANDEX_MAP_TOKEN = os.getenv("YANDEX_MAP_TOKEN")
YANDEX_GEOCODER_TOKEN = os.getenv("YANDEX_GEOCODER_TOKEN")
YANDEX_DELIVERY_TOKEN = os.getenv("YANDEX_DELIVERY_TOKEN")

YOOKASSA_SECRET_KEY = os.getenv("YOOKASSA_SECRET_KEY")
YOOKASSA_SHOP_ID = os.getenv("YOOKASSA_SHOP_ID")
YOOKASSA_API_URL = os.getenv("YOOKASSA_API_URL")

MANAGER_USER = os.getenv("MANAGER_USER")
MANAGER_PASS = os.getenv("MANAGER_PASS")

PRIZEDRAW_BOT_TOKEN = os.getenv("PRIZEDRAW_BOT_TOKEN")
AMOCRM_CLIENT_SECRET = os.getenv("AMOCRM_CLIENT_SECRET")
AMOCRM_CLIENT_ID = os.getenv("AMOCRM_CLIENT_ID")
AMOCRM_LONG_TOKEN = os.getenv("AMOCRM_LONG_TOKEN")
AMOCRM_AUTH_CODE = os.getenv("AMOCRM_AUTH_CODE")
AMOCRM_REDIRECT_URI = os.getenv("AMOCRM_REDIRECT_URI")
AMOCRM_BASE_DOMAIN = os.getenv("AMOCRM_BASE_DOMAIN")
AMOCRM_ACCESS_TOKEN = os.getenv("AMOCRM_ACCESS_TOKEN")
AMOCRM_REFRESH_TOKEN = os.getenv("AMOCRM_REFRESH_TOKEN")
