"""FastAPI ilovasi: API + Telegram webhook + Mini App (bitta servis)."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api import api_router
from app.config import settings

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
)
log = logging.getLogger("dxl_erp")

BASE_DIR = Path(__file__).resolve().parent.parent
WEB_DIST = BASE_DIR / settings.web_dist


async def _run_migrations() -> None:
    """Ishga tushishda sxemani yangilaydi."""
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(BASE_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BASE_DIR / "migrations"))
    cfg.set_main_option("sqlalchemy.url", settings.database_url)

    import asyncio

    def _upgrade() -> None:
        command.upgrade(cfg, "head")

    await asyncio.to_thread(_upgrade)
    log.info("Migratsiyalar qo'llandi")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.auto_migrate:
        try:
            await _run_migrations()
        except Exception:
            log.exception("Migratsiya xatosi — ilova baribir ishga tushmoqda")

    from app.db import session_scope
    from app.services.settings_service import ensure_defaults

    try:
        async with session_scope() as session:
            await ensure_defaults(session)
            from app.services.stock import main_warehouse

            await main_warehouse(session)
    except Exception:
        log.exception("Boshlang'ich sozlamalarni yaratishda xato")

    if settings.seed_demo:
        try:
            from seed.demo import seed_demo_data

            await seed_demo_data()
        except Exception:
            log.exception("Demo ma'lumot yuklanmadi")

    from app.bot.bot import close_bot, fetch_bot_username, setup_webhook

    try:
        await fetch_bot_username()
        await setup_webhook()
    except Exception:
        log.exception("Telegram webhook o'rnatilmadi")

    from app.jobs.scheduler import start_scheduler, stop_scheduler

    try:
        start_scheduler()
    except Exception:
        log.exception("Scheduler ishga tushmadi")

    yield

    stop_scheduler()
    await close_bot()


app = FastAPI(
    title="DXL Dental Implant ERP",
    version=__version__,
    lifespan=lifespan,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Mini App Telegram domenidan ochiladi
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_prefix)


@app.get("/api/health")
async def health() -> dict:
    return {"ok": True, "version": __version__, "tz": settings.tz}


@app.post("/tg/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> JSONResponse:
    """Telegram'dan kelgan yangilanishlarni aiogram'ga uzatadi."""
    if x_telegram_bot_api_secret_token != settings.webhook_secret:
        raise HTTPException(status_code=403, detail="Noto'g'ri secret token")

    from aiogram.types import Update

    from app.bot.bot import get_bot, get_dispatcher

    bot = get_bot()
    if bot is None:
        raise HTTPException(status_code=503, detail="Bot sozlanmagan")

    update = Update.model_validate(await request.json(), context={"bot": bot})
    await get_dispatcher().feed_update(bot, update)
    return JSONResponse({"ok": True})


# ------------------------------------------------------------- Mini App (SPA)
if WEB_DIST.exists():
    assets = WEB_DIST / "assets"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{full_path:path}")
    async def spa(full_path: str) -> FileResponse:
        """Har qanday yo'l uchun SPA index.html — client-side routing."""
        candidate = WEB_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(WEB_DIST / "index.html")

else:  # pragma: no cover - faqat frontend yig'ilmagan holatda

    @app.get("/")
    async def no_frontend() -> dict:
        return {
            "ok": True,
            "message": (
                "Mini App yig'ilmagan. `cd web && npm install && npm run build` "
                "buyrug'ini bajaring."
            ),
        }
