"""Bildirishnomalarni yuborish (rol yoki foydalanuvchi bo'yicha)."""

from __future__ import annotations

import logging
from collections.abc import Sequence

from aiogram.exceptions import TelegramAPIError
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Notification, Role, User, utcnow

log = logging.getLogger(__name__)


def webapp_button(text: str, path: str = "/") -> InlineKeyboardMarkup:
    """Mini App'ning kerakli sahifasini ochadigan tugma."""
    url = f"{settings.webapp_url}{path}"
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=text, web_app=WebAppInfo(url=url))]]
    )


async def _deliver(chat_id: int, text: str, markup: InlineKeyboardMarkup | None) -> str | None:
    """Xabarni yuboradi. Xato bo'lsa matnini qaytaradi."""
    from app.bot.bot import get_bot

    bot = get_bot()
    if bot is None:
        log.info("[bildirishnoma o'chirilgan] %s: %s", chat_id, text[:120])
        return "BOT_TOKEN sozlanmagan"
    try:
        await bot.send_message(chat_id, text, reply_markup=markup)
        return None
    except TelegramAPIError as exc:  # bloklagan, chat topilmadi va h.k.
        log.warning("Xabar yuborilmadi (%s): %s", chat_id, exc)
        return str(exc)


async def send_to_user(
    session: AsyncSession,
    user: User,
    text: str,
    *,
    kind: str = "info",
    dedup_key: str | None = None,
    button: tuple[str, str] | None = None,
) -> bool:
    """Bitta foydalanuvchiga xabar. `dedup_key` takrorlanishning oldini oladi."""
    if dedup_key:
        already = (
            await session.execute(
                select(Notification.id).where(
                    Notification.user_id == user.id,
                    Notification.dedup_key == dedup_key,
                    Notification.delivered.is_(True),
                )
            )
        ).scalar_one_or_none()
        if already is not None:
            return False

    markup = webapp_button(*button) if button else None
    error = None
    if user.telegram_id:
        error = await _deliver(user.telegram_id, text, markup)
    else:
        error = "Telegram hisobi ulanmagan"

    session.add(
        Notification(
            created_at=utcnow(),
            user_id=user.id,
            kind=kind,
            dedup_key=dedup_key,
            text=text,
            delivered=error is None,
            error=error,
        )
    )
    await session.flush()
    return error is None


async def send_to_roles(
    session: AsyncSession,
    roles: Sequence[Role],
    text: str,
    *,
    kind: str = "info",
    dedup_key: str | None = None,
    button: tuple[str, str] | None = None,
) -> int:
    """Rol(lar) bo'yicha barcha faol foydalanuvchilarga."""
    users = (
        await session.execute(
            select(User).where(User.role.in_(list(roles)), User.is_active.is_(True))
        )
    ).scalars().all()
    sent = 0
    for user in users:
        if await send_to_user(
            session, user, text, kind=kind, dedup_key=dedup_key, button=button
        ):
            sent += 1
    return sent


async def send_to_user_id(
    session: AsyncSession,
    user_id: int | None,
    text: str,
    *,
    kind: str = "info",
    dedup_key: str | None = None,
    button: tuple[str, str] | None = None,
) -> bool:
    if not user_id:
        return False
    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        return False
    return await send_to_user(
        session, user, text, kind=kind, dedup_key=dedup_key, button=button
    )
