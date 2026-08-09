"""Telegram bot — Mini App'ga kirish nuqtasi va bildirishnomalar kanali."""

from __future__ import annotations

import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app.config import settings, webhook_url_problem

log = logging.getLogger(__name__)

_bot: Bot | None = None
_dp: Dispatcher | None = None


def get_bot() -> Bot | None:
    """Bot obyekti (BOT_TOKEN sozlanmagan bo'lsa None)."""
    global _bot
    if _bot is None and settings.bot_token:
        _bot = Bot(
            token=settings.bot_token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
    return _bot


def get_dispatcher() -> Dispatcher:
    global _dp
    if _dp is None:
        from aiogram.types import ErrorEvent

        from app.bot.handlers import start

        _dp = Dispatcher(storage=MemoryStorage())
        _dp.include_router(start.router)

        @_dp.errors()
        async def on_error(event: ErrorEvent) -> bool:
            """Har qanday xatoni logga yozadi va foydalanuvchini jim qoldirmaydi."""
            log.exception("Bot xatosi: %s", event.exception)
            message = getattr(event.update, "message", None)
            if message is not None:
                try:
                    await message.answer(
                        "⚠️ Texnik nosozlik yuz berdi. Biroz kutib qayta urinib ko'ring.\n"
                        "Muammo davom etsa rahbaringizga xabar bering."
                    )
                except Exception:  # javob ham ketmasa — faqat logda qoladi
                    log.exception("Xato haqida xabar yuborilmadi")
            return True

    return _dp


_bot_username: str | None = None


async def fetch_bot_username() -> str:
    """Bot username — taklif havolalarini yasash uchun."""
    global _bot_username
    if _bot_username:
        return _bot_username
    if settings.bot_username:
        _bot_username = settings.bot_username.lstrip("@")
        return _bot_username
    bot = get_bot()
    if bot is None:
        return ""
    try:
        me = await bot.get_me()
        _bot_username = me.username or ""
    except Exception as exc:  # pragma: no cover - tarmoq xatosi
        log.warning("Bot username aniqlanmadi: %s", exc)
        _bot_username = ""
    return _bot_username


def bot_username() -> str:
    return _bot_username or settings.bot_username.lstrip("@")


async def setup_webhook() -> None:
    bot = get_bot()
    if bot is None:
        log.warning("BOT_TOKEN sozlanmagan — bot ishga tushmadi")
        return
    url = f"{settings.webapp_url}/tg/webhook"

    problem = webhook_url_problem(settings.webapp_url)
    if problem is not None:
        current = settings.webapp_url or "(bo'sh)"
        message = (
            f"WEBAPP_URL yaroqsiz ({problem}). Hozirgi qiymat: «{current}». "
            "Railway'da Variables -> WEBAPP_URL ni servis domeningizga to'g'rilang, "
            "masalan: https://dxl-erp-production.up.railway.app"
        )
        log.error("%s", message)
        raise ValueError(message)

    await bot.set_webhook(
        url=url,
        secret_token=settings.webhook_secret,
        drop_pending_updates=True,
        allowed_updates=["message", "callback_query", "my_chat_member"],
    )

    # Telegram haqiqatan ham qabul qilganini tekshiramiz
    info = await bot.get_webhook_info()
    if info.url == url:
        log.info("Telegram webhook o'rnatildi: %s", url)
    else:
        log.error(
            "Webhook mos kelmadi! Telegram'da: «%s», kutilgan: «%s». "
            "WEBAPP_URL ni Railway bergan domenga to'g'rilang.",
            info.url or "(bo'sh)",
            url,
        )
    if info.last_error_message:
        log.error(
            "Telegram webhook'ga yeta olmayapti: %s (%s)",
            info.last_error_message,
            info.last_error_date,
        )


async def close_bot() -> None:
    global _bot
    if _bot is not None:
        await _bot.session.close()
        _bot = None
