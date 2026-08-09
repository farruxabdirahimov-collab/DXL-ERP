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
from app.config import db_host, is_placeholder_db, settings

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

#: Bazaga ulanish va migratsiya uchun eng ko'p kutish vaqti.
#: Qayta urinishlar va migratsiya shu ichiga sig'ishi kerak (healthcheck kutmaydi).
DB_STARTUP_TIMEOUT = 240
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


async def _try_connect(url: str) -> str | None:
    """Manzilga ulanib ko'radi. Xato bo'lsa sababini qaytaradi."""
    from sqlalchemy import text

    from app.db import make_engine

    probe = make_engine(url)
    try:
        async with probe.connect() as connection:
            await connection.execute(text("SELECT 1"))
        return None
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}"
    finally:
        await probe.dispose()


#: Ichki tarmoq konteyner ishga tushgandan keyin bir necha soniya kechikadi —
#: shuning uchun asosiy manzilga bir necha marta urinamiz
DB_RETRIES = 6
DB_RETRY_DELAY = 5


async def _select_database() -> None:
    """Ichki manzil ishlamasa, `DATABASE_PUBLIC_URL` zaxirasiga o'tadi."""
    from app import db as db_module

    primary = settings.database_url

    # Eng ko'p uchraydigan xato: `.env.example` dagi namuna qiymat ko'chirilgan
    if is_placeholder_db(primary):
        hint = (
            f"DATABASE_URL da namuna qiymat qolib ketgan («{db_host(primary)}»). "
            "Railway'da Variables -> DATABASE_URL qiymatini "
            "${{Postgres.DATABASE_URL}} qilib qo'ying (qo'lda yozmang, "
            "Railway taklif qilgan ro'yxatdan tanlang)."
        )
        STATE["db_hint"] = hint
        log.error("%s", hint)
        raise RuntimeError(hint)

    log.info("Bazaga ulanmoqda: %s", db_host(primary))

    error = None
    for attempt in range(1, DB_RETRIES + 1):
        error = await _try_connect(primary)
        if error is None:
            if attempt > 1:
                log.info("Baza %s-urinishda ulandi", attempt)
            return
        if attempt < DB_RETRIES:
            log.warning(
                "Baza ulanmadi (%s/%s): %s — %s soniyadan keyin qayta urinamiz",
                attempt, DB_RETRIES, error, DB_RETRY_DELAY,
            )
            await asyncio.sleep(DB_RETRY_DELAY)

    log.error("Baza manzili ishlamadi (%s): %s", db_host(primary), error)

    fallback = settings.database_public_url
    if not fallback or fallback == primary:
        STATE["db_hint"] = (
            f"«{db_host(primary)}» manzili topilmadi. Railway'da DATABASE_URL ni "
            "${{Postgres.DATABASE_URL}} deb yozing yoki zaxira sifatida "
            "DATABASE_PUBLIC_URL o'zgaruvchisini qo'shing."
        )
        raise RuntimeError(f"Bazaga ulanib bo'lmadi: {error}")

    log.warning("Zaxira manzilga o'tilmoqda: %s", db_host(fallback))
    fallback_error = await _try_connect(fallback)
    if fallback_error is not None:
        STATE["db_hint"] = (
            f"Ikkala manzil ham ishlamadi: {db_host(primary)} va {db_host(fallback)}"
        )
        raise RuntimeError(f"Zaxira manzil ham ishlamadi: {fallback_error}")

    await db_module.rebind(fallback)
    STATE["db_manzil"] = db_host(fallback)
    log.info("Zaxira manzil ishladi: %s", db_host(fallback))


async def _prepare_database() -> None:
    """Migratsiya + boshlang'ich sozlamalar. Sekin bo'lishi mumkin."""
    await _select_database()
    STATE.setdefault("db_manzil", db_host(settings.database_url))

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
        STATE["error"] = STATE.get("db_hint") or str(exc)
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


@app.get("/api/diagnostics")
async def diagnostics() -> dict:
    """Sozlash bosqichida muammoni topish uchun. Maxfiy qiymatlar ko'rsatilmaydi."""
    from sqlalchemy import func, select

    result: dict = {
        "version": __version__,
        "state": dict(STATE),
        "config": {
            "bot_token_sozlangan": bool(settings.bot_token),
            "webapp_url": settings.webapp_url,
            "webhook_secret_sozlangan": settings.webhook_secret != "dxl-erp-secret",
            "superadmin_telegram_id": settings.superadmin_telegram_id or None,
            "database_manzil": db_host(settings.database_url),
            "database_public_url_sozlangan": bool(settings.database_public_url),
            "tz": settings.tz,
            "auto_migrate": settings.auto_migrate,
        },
        "mini_app_yigilgan": WEB_DIST.exists(),
    }

    # --- Baza holati ---
    try:
        from app.db import session_scope
        from app.models import Product, User

        async with session_scope() as session:
            users = (await session.execute(select(func.count(User.id)))).scalar_one()
            products = (
                await session.execute(select(func.count(Product.id)))
            ).scalar_one()
        result["baza"] = {
            "ulanish": "ok",
            "foydalanuvchilar": int(users),
            "mahsulotlar": int(products),
        }
    except Exception as exc:
        result["baza"] = {"ulanish": "xato", "sabab": str(exc)[:300]}

    # --- Telegram webhook holati ---
    from app.bot.bot import get_bot

    bot = get_bot()
    if bot is None:
        result["telegram"] = {"holat": "BOT_TOKEN sozlanmagan"}
    else:
        try:
            info = await asyncio.wait_for(bot.get_webhook_info(), timeout=15)
            result["telegram"] = {
                "holat": "ok",
                "webhook_url": info.url or "(o'rnatilmagan)",
                "kutayotgan_xabarlar": info.pending_update_count,
                "oxirgi_xato": info.last_error_message,
                "kutilgan_url": f"{settings.webapp_url}/tg/webhook",
                "url_mos": info.url == f"{settings.webapp_url}/tg/webhook",
            }
        except Exception as exc:
            result["telegram"] = {"holat": "xato", "sabab": str(exc)[:300]}

    return result


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
