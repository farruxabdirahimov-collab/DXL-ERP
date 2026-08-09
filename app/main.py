"""FastAPI ilovasi: API + Telegram webhook + Mini App (bitta servis)."""

from __future__ import annotations

import asyncio
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


#: Ishga tushish bosqichlari holati — `/api/health` va `/api/ready` shundan o'qiydi
STATE: dict[str, object] = {
    "db": "kutilmoqda",
    "bot": "kutilmoqda",
    "scheduler": "kutilmoqda",
    "ready": False,
    "error": None,
}

#: Bazaga ulanish va migratsiya uchun eng ko'p kutish vaqti
DB_STARTUP_TIMEOUT = 90
#: Telegram bilan bog'lanish uchun eng ko'p kutish vaqti
BOT_STARTUP_TIMEOUT = 30


async def _run_migrations() -> None:
    """Ishga tushishda sxemani yangilaydi."""
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(BASE_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BASE_DIR / "migrations"))
    cfg.set_main_option("sqlalchemy.url", settings.database_url)

    def _upgrade() -> None:
        command.upgrade(cfg, "head")

    await asyncio.to_thread(_upgrade)
    log.info("Migratsiyalar qo'llandi")


async def _prepare_database() -> None:
    """Migratsiya + boshlang'ich sozlamalar. Sekin bo'lishi mumkin."""
    if settings.auto_migrate:
        await _run_migrations()

    from app.db import session_scope
    from app.services.settings_service import ensure_defaults
    from app.services.stock import main_warehouse

    async with session_scope() as session:
        await ensure_defaults(session)
        await main_warehouse(session)


async def _bootstrap() -> None:
    """Server so'rovlarni qabul qila boshlagandan KEYIN fonda bajariladi.

    Bazaga yoki Telegram'ga ulanish sekin bo'lsa ham `/api/health` javob beraveradi —
    aks holda platformaning healthcheck'i konteynerni o'lik deb hisoblaydi.
    """
    try:
        await asyncio.wait_for(_prepare_database(), timeout=DB_STARTUP_TIMEOUT)
        STATE["db"] = "tayyor"
    except asyncio.TimeoutError:
        STATE["db"] = "xato: bazaga ulanib bo'lmadi (vaqt tugadi)"
        STATE["error"] = (
            "DATABASE_URL tekshiring: baza xosti javob bermayapti. "
            "Railway'da PostgreSQL servisi ulanganmi va o'zgaruvchi to'g'rimi?"
        )
        log.error("Bazaga %s soniyada ulanib bo'lmadi — DATABASE_URL ni tekshiring",
                  DB_STARTUP_TIMEOUT)
    except Exception as exc:
        STATE["db"] = f"xato: {exc}"
        STATE["error"] = str(exc)
        log.exception("Bazani tayyorlashda xato")

    if settings.seed_demo:
        try:
            from seed.demo import seed_demo_data

            await seed_demo_data()
        except Exception:
            log.exception("Demo ma'lumot yuklanmadi")

    from app.bot.bot import fetch_bot_username, setup_webhook

    if not settings.bot_token:
        STATE["bot"] = "o'chirilgan: BOT_TOKEN sozlanmagan"
        log.warning("BOT_TOKEN sozlanmagan — bot va bildirishnomalar ishlamaydi")
    else:
        try:
            await asyncio.wait_for(fetch_bot_username(), timeout=BOT_STARTUP_TIMEOUT)
            await asyncio.wait_for(setup_webhook(), timeout=BOT_STARTUP_TIMEOUT)
            STATE["bot"] = "tayyor"
        except asyncio.TimeoutError:
            STATE["bot"] = "xato: Telegram javob bermadi"
            log.error("Telegram bilan bog'lanib bo'lmadi (vaqt tugadi)")
        except Exception as exc:
            STATE["bot"] = f"xato: {exc}"
            log.exception("Telegram webhook o'rnatilmadi")

    from app.jobs.scheduler import start_scheduler

    try:
        start_scheduler()
        STATE["scheduler"] = "tayyor"
    except Exception as exc:
        STATE["scheduler"] = f"xato: {exc}"
        log.exception("Scheduler ishga tushmadi")

    STATE["ready"] = STATE["db"] == "tayyor"
    log.info("Ishga tushish yakunlandi: %s", STATE)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Sekin ishlarni fonga qo'yamiz — server darhol so'rov qabul qila boshlaydi
    task = asyncio.create_task(_bootstrap())

    yield

    task.cancel()

    from app.bot.bot import close_bot
    from app.jobs.scheduler import stop_scheduler

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
    """Platformaning healthcheck'i. Har doim 200 qaytaradi.

    Baza yoki Telegram bilan muammo bo'lsa ham konteyner o'ldirilmasligi kerak —
    muammo `state` ichida ko'rinadi va loglarga yoziladi.
    """
    return {
        "ok": True,
        "version": __version__,
        "tz": settings.tz,
        "state": dict(STATE),
    }


@app.get("/api/ready")
async def ready() -> JSONResponse:
    """Batafsil tayyorlik holati (baza ulanmagan bo'lsa 503)."""
    payload = {"version": __version__, **STATE}
    return JSONResponse(payload, status_code=200 if STATE["ready"] else 503)


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
