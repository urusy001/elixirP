from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from uvicorn import Server, Config

from config import BASE_DIR, templates
from src.webapp.routes import *

app = FastAPI(title="ElixirPeptides")
app.mount("/static", StaticFiles(directory=BASE_DIR / "src" / "webapp" / "static"), name="static")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8000", "http://localhost:8000", "https://elixirpeptides.devsivanschostakov.org"],  # your frontend origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(product_router)
app.include_router(search_router)
app.include_router(cart_router)
app.include_router(cdek_router)
app.include_router(yandex_router)
app.include_router(payments_router)
app.include_router(users_router)
app.include_router(forwarding_router)
app.include_router(webhooks_router)

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

async def run_app():
    server = Server(Config(app, reload=True, log_config=None))
    await server.serve()
