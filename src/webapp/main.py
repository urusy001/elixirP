from fastapi import FastAPI, Request, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from uvicorn import Server, Config

from config import BASE_DIR, templates, API_PREFIX
from src.webapp.routes import *

app = FastAPI(title="ElixirPeptides")
app.mount("/static", StaticFiles(directory=BASE_DIR / "src" / "webapp" / "static", html=True), name="static")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8000", "http://localhost:8000", "https://www.devsivanschostakov.org",
                   "https://www.devsivanschostakov.org"],  # your frontend origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(product_router, prefix=API_PREFIX)
app.include_router(search_router, prefix=API_PREFIX)
app.include_router(cart_router, prefix=API_PREFIX)
app.include_router(cdek_router, prefix=API_PREFIX)
app.include_router(yandex_router, prefix=API_PREFIX)
app.include_router(payments_router, prefix=API_PREFIX)
app.include_router(users_router, prefix=API_PREFIX)
app.include_router(auth_router, prefix=API_PREFIX)
app.include_router(favourite_router, prefix=API_PREFIX),
app.include_router(categories_router, prefix=API_PREFIX),
app.include_router(webhooks_router)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/test", response_class=HTMLResponse)
async def test(request: Request):
    return templates.TemplateResponse("test.html", {"request": request})

@app.get("/product/{path:path}", response_class=HTMLResponse)
async def spa_product(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

async def run_app():
    server = Server(Config(app, reload=True, log_config=None))
    await server.serve()
