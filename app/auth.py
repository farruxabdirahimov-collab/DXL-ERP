"""Telegram Mini App autentifikatsiyasi va rol tekshiruvi."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from collections.abc import Sequence
from datetime import timedelta
from urllib.parse import parse_qsl

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.models import Doctor, Role, User, utcnow

log = logging.getLogger(__name__)

#: initData shu muddatdan eski bo'lsa qabul qilinmaydi
INIT_DATA_MAX_AGE = timedelta(hours=24)


class TelegramAuthError(Exception):
    pass


def verify_init_data(init_data: str, bot_token: str) -> dict:
    """Telegram `initData` imzosini tekshiradi va foydalanuvchi ma'lumotini qaytaradi.

    https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
    """
    if not init_data:
        raise TelegramAuthError("initData bo'sh")

    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = pairs.pop("hash", None)
    if not received_hash:
        raise TelegramAuthError("hash yo'q")

    data_check_string = "\n".join(f"{k}={pairs[k]}" for k in sorted(pairs))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected, received_hash):
        raise TelegramAuthError("imzo mos kelmadi")

    auth_date = pairs.get("auth_date")
    if auth_date:
        try:
            issued = int(auth_date)
        except ValueError as exc:
            raise TelegramAuthError("auth_date noto'g'ri") from exc
        age = utcnow().timestamp() - issued
        if age > INIT_DATA_MAX_AGE.total_seconds():
            raise TelegramAuthError("initData muddati o'tgan, ilovani qayta oching")

    user_raw = pairs.get("user")
    if not user_raw:
        raise TelegramAuthError("user ma'lumoti yo'q")
    try:
        return json.loads(user_raw)
    except json.JSONDecodeError as exc:
        raise TelegramAuthError("user JSON buzuq") from exc


async def _bootstrap_superadmin(session: AsyncSession, tg_user: dict) -> User | None:
    """Birinchi kirish: `SUPERADMIN_TELEGRAM_ID` avtomatik super-admin bo'ladi."""
    tg_id = int(tg_user["id"])
    if not settings.superadmin_telegram_id or tg_id != settings.superadmin_telegram_id:
        return None

    name = " ".join(
        p for p in (tg_user.get("first_name"), tg_user.get("last_name")) if p
    ) or f"Admin {tg_id}"
    user = User(
        telegram_id=tg_id,
        telegram_username=tg_user.get("username"),
        full_name=name,
        role=Role.SUPERADMIN,
        is_active=True,
    )
    session.add(user)
    await session.flush()
    log.info("Super-admin yaratildi: telegram_id=%s", tg_id)
    return user


async def get_current_user(
    session: AsyncSession = Depends(get_session),
    x_telegram_init_data: str | None = Header(default=None),
    x_debug_telegram_id: str | None = Header(default=None),
) -> User:
    """Joriy foydalanuvchi. Har so'rovda initData qayta tekshiriladi."""
    tg_user: dict

    if settings.bot_token:
        try:
            tg_user = verify_init_data(x_telegram_init_data or "", settings.bot_token)
        except TelegramAuthError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Kirish rad etildi: {exc}"
            ) from exc
    else:
        # Lokal ishlab chiqish rejimi: BOT_TOKEN ko'rsatilmagan.
        if not x_debug_telegram_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="BOT_TOKEN sozlanmagan va X-Debug-Telegram-Id berilmadi",
            )
        tg_user = {"id": int(x_debug_telegram_id), "first_name": "Dev"}

    tg_id = int(tg_user["id"])
    user = (
        await session.execute(select(User).where(User.telegram_id == tg_id))
    ).scalar_one_or_none()

    if user is None:
        user = await _bootstrap_superadmin(session, tg_user)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Siz tizimga qo'shilmagansiz. Rahbaringizdan taklif havolasini so'rang "
                "yoki vrach bo'lsangiz botda telefon raqamingizni yuboring."
            ),
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Hisobingiz faolsizlantirilgan"
        )

    # Profilni yangilab turamiz
    changed = False
    if tg_user.get("username") and user.telegram_username != tg_user["username"]:
        user.telegram_username = tg_user["username"]
        changed = True
    now = utcnow()
    if user.last_seen_at is None or (now - user.last_seen_at) > timedelta(minutes=5):
        user.last_seen_at = now
        changed = True
    if changed:
        await session.flush()

    return user


def require_role(*roles: Role):
    """Endpoint uchun rol talabi: `Depends(require_role(Role.DIRECTOR, ...))`."""
    allowed = set(roles)

    async def _checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bu bo'limga sizning rolingizda ruxsat yo'q",
            )
        return user

    return _checker


def has_role(user: User, roles: Sequence[Role]) -> bool:
    return user.role in set(roles)


def require_perm(permission: str):
    """Ruxsat kaliti bo'yicha himoya: `Depends(require_perm(PRODUCTS_EDIT))`.

    Qo'shimcha rollar ham hisobga olinadi.
    """
    from app.permissions import user_can

    async def _checker(user: User = Depends(get_current_user)) -> User:
        if not user_can(user, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bu amalga sizning rolingizda ruxsat yo'q",
            )
        return user

    return _checker


async def current_doctor(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Doctor:
    """Vrach roli uchun — o'ziga bog'langan vrach kartochkasi."""
    if user.role is not Role.DOCTOR:
        raise HTTPException(status_code=403, detail="Faqat vrachlar uchun")
    doctor = (
        await session.execute(select(Doctor).where(Doctor.user_id == user.id))
    ).scalar_one_or_none()
    if doctor is None:
        raise HTTPException(
            status_code=404, detail="Vrach kartochkangiz topilmadi, agentingizga murojaat qiling"
        )
    return doctor
