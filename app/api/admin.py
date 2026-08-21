"""Boshqaruv: foydalanuvchilar, taklifnomalar, sozlamalar, audit jurnali."""

from __future__ import annotations

import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_perm
from app.config import settings as app_settings
from app.db import get_session
from app.models import (
    ROLE_LABELS_UZ,
    AuditLog,
    Invite,
    Role,
    Setting,
    User,
    utcnow,
)
from app.permissions import AUDIT_VIEW, SETTINGS_MANAGE, USERS_MANAGE, permissions_for
from app.schemas import (
    AuditOut,
    InviteCreateIn,
    InviteOut,
    OkOut,
    SettingIn,
    UserCreateIn,
    UserOut,
    UserUpdateIn,
)
from app.services import stock as stock_service
from app.services.settings_service import DEFAULT_SETTINGS, get_settings_map, set_setting
from app.utils.audit import log_action

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/roles")
async def list_roles(_: User = Depends(require_perm(USERS_MANAGE))):
    """Rollar ro'yxati va har birining ruxsatlari — foydalanuvchi qo'shishda kerak."""
    return [
        {
            "value": role.value,
            "label": ROLE_LABELS_UZ[role],
            "permissions": permissions_for(role),
        }
        for role in Role
    ]


@router.get("/users", response_model=list[UserOut])
async def list_users(
    role: Role | None = None,
    only_active: bool = True,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_perm(USERS_MANAGE)),
):
    stmt = select(User).order_by(User.role, User.full_name)
    if role is not None:
        stmt = stmt.where(User.role == role)
    if only_active:
        stmt = stmt.where(User.is_active.is_(True))
    return (await session.execute(stmt)).scalars().all()


@router.get("/agents", response_model=list[UserOut])
async def list_agents(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_perm(USERS_MANAGE)),
):
    return (
        await session.execute(
            select(User)
            .where(User.role == Role.AGENT, User.is_active.is_(True))
            .order_by(User.full_name)
        )
    ).scalars().all()


@router.post("/users", response_model=UserOut, status_code=201)
async def create_user(
    payload: UserCreateIn,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(require_perm(USERS_MANAGE)),
):
    if payload.telegram_id:
        exists = (
            await session.execute(
                select(User).where(User.telegram_id == payload.telegram_id)
            )
        ).scalar_one_or_none()
        if exists is not None:
            raise HTTPException(409, "Bu Telegram ID allaqachon ro'yxatdan o'tgan")

    data = payload.model_dump()
    data["extra_roles"] = [r.value for r in payload.extra_roles if r is not payload.role]
    user = User(**data, is_active=True, created_by_id=actor.id)
    session.add(user)
    await session.flush()

    if user.role is Role.AGENT and user.has_own_stock:
        await stock_service.ensure_agent_warehouse(session, user)

    await log_action(session, actor, "create", "user", user.id, new=payload.model_dump())
    return user


@router.patch("/users/{user_id}", response_model=UserOut)
async def update_user(
    user_id: int,
    payload: UserUpdateIn,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(require_perm(USERS_MANAGE)),
):
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(404, "Xodim topilmadi")
    if user.id == actor.id and payload.is_active is False:
        raise HTTPException(400, "O'zingizni faolsizlantira olmaysiz")

    changes = payload.model_dump(exclude_unset=True)
    if changes.get("extra_roles") is not None:
        primary = changes.get("role") or user.role
        changes["extra_roles"] = [
            r.value for r in payload.extra_roles or [] if r is not primary
        ]
    old = {key: getattr(user, key) for key in changes}
    for key, value in changes.items():
        setattr(user, key, value)
    await session.flush()

    if user.role is Role.AGENT and user.has_own_stock:
        await stock_service.ensure_agent_warehouse(session, user)

    await log_action(session, actor, "update", "user", user_id, old=old, new=changes)
    return user


@router.post("/invites", response_model=InviteOut, status_code=201)
async def create_invite(
    payload: InviteCreateIn,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(require_perm(USERS_MANAGE)),
):
    """Xodim uchun bir martalik taklif havolasi — u botga /start bilan kiradi."""
    invite = Invite(
        token=secrets.token_urlsafe(12),
        role=payload.role,
        full_name=payload.full_name,
        phone=payload.phone,
        has_own_stock=payload.has_own_stock,
        extra_roles=[r.value for r in payload.extra_roles if r is not payload.role],
        expires_at=utcnow() + timedelta(days=payload.valid_days),
        created_by_id=actor.id,
    )
    session.add(invite)
    await session.flush()
    await log_action(
        session, actor, "invite", "user", invite.id,
        new={"role": payload.role.value, "full_name": payload.full_name},
    )

    return _with_link(invite)


def _with_link(invite: Invite) -> InviteOut:
    """Taklifnomaga bosiladigan havola qo'shadi."""
    from app.bot.bot import bot_username

    out = InviteOut.model_validate(invite)
    username = bot_username()
    out.link = (
        f"https://t.me/{username}?start=inv_{invite.token}"
        if username
        else f"/start inv_{invite.token}"
    )
    return out


@router.get("/invites", response_model=list[InviteOut])
async def list_invites(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_perm(USERS_MANAGE)),
):
    """Ishlatilmagan taklifnomalar — har birida tayyor havola bilan."""
    rows = (
        await session.execute(
            select(Invite).where(Invite.used_at.is_(None)).order_by(Invite.id.desc())
        )
    ).scalars().all()
    return [_with_link(invite) for invite in rows]


@router.post("/seed-catalog", response_model=OkOut)
async def seed_catalog(
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(require_perm(USERS_MANAGE)),
):
    """Boshlang'ich DXL katalogini yuklaydi (103 ta namunaviy SKU).

    Keyin uni Excel orqali o'z prays-listingiz bilan almashtirish mumkin.
    Mahsulotlar SKU bo'yicha yangilanadi, ombor qoldig'iga tegilmaydi.
    """
    from seed.load import seed_products, seed_tariffs

    created, updated = await seed_products(session)
    tariffs = await seed_tariffs(session)
    await log_action(
        session, actor, "import", "product", None,
        new={"yangi": created, "yangilandi": updated, "manba": "boshlangich katalog"},
    )
    message = f"Katalog yuklandi: {created} ta yangi, {updated} tasi yangilandi"
    if tariffs:
        message += f". {tariffs} ta boshlang'ich tarif ham qo'shildi"
    return OkOut(ok=True, message=message)


@router.delete("/invites/{invite_id}", response_model=OkOut)
async def delete_invite(
    invite_id: int,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(require_perm(USERS_MANAGE)),
):
    invite = await session.get(Invite, invite_id)
    if invite is None:
        raise HTTPException(404, "Taklifnoma topilmadi")
    if invite.used_at is not None:
        raise HTTPException(400, "Bu taklifnoma allaqachon ishlatilgan")
    await session.delete(invite)
    await log_action(session, actor, "delete", "invite", invite_id)
    return OkOut(ok=True, message="Taklifnoma bekor qilindi")


@router.post("/reset-webhook")
async def reset_webhook(
    actor: User = Depends(require_perm(SETTINGS_MANAGE)),
):
    """Telegram webhook'ini qayta o'rnatadi va natijasini qaytaradi.

    Bot javob bermay qolsa — deploy qilmasdan shu tugma bilan tiklash mumkin.
    """
    from app.bot.bot import get_bot, setup_webhook

    bot = get_bot()
    if bot is None:
        raise HTTPException(400, "BOT_TOKEN sozlanmagan")

    kutilgan = f"{app_settings.webapp_url}/tg/webhook"
    try:
        await setup_webhook()
    except Exception as exc:
        raise HTTPException(
            400,
            f"Webhook o'rnatilmadi.\n\nUrinilgan manzil: {kutilgan}\n\nSabab: {exc}",
        ) from exc

    info = await bot.get_webhook_info()
    return {
        "ok": info.url == kutilgan,
        "webhook_url": info.url or "(bo'sh)",
        "kutilgan_url": kutilgan,
        "oxirgi_xato": info.last_error_message,
        "kutayotgan_xabarlar": info.pending_update_count,
        "message": (
            "Webhook o'rnatildi — botga /start yozib ko'ring"
            if info.url == kutilgan
            else "Webhook mos kelmadi, WEBAPP_URL ni tekshiring"
        ),
    }


# --------------------------------------------------------------- sozlamalar
@router.get("/settings")
async def read_settings(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_perm(SETTINGS_MANAGE)),
):
    values = await get_settings_map(session)
    return [
        {"key": key, "value": values.get(key), "label_uz": label}
        for key, (_, label) in DEFAULT_SETTINGS.items()
    ]


@router.put("/settings", response_model=OkOut)
async def write_setting(
    payload: SettingIn,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(require_perm(SETTINGS_MANAGE)),
):
    if payload.key not in DEFAULT_SETTINGS:
        raise HTTPException(400, f"Noma'lum sozlama: {payload.key}")
    old = await session.get(Setting, payload.key)
    await set_setting(session, payload.key, payload.value)
    await log_action(
        session, actor, "update", "setting", payload.key,
        old={"value": old.value if old else None}, new={"value": payload.value},
    )
    return OkOut(ok=True, message="Sozlama saqlandi")


# --------------------------------------------------------------------- audit
@router.get("/audit", response_model=list[AuditOut])
async def audit_log(
    entity: str | None = None,
    action: str | None = None,
    user_id: int | None = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_perm(AUDIT_VIEW)),
):
    stmt = select(AuditLog).order_by(AuditLog.id.desc()).limit(limit).offset(offset)
    if entity:
        stmt = stmt.where(AuditLog.entity == entity)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if user_id:
        stmt = stmt.where(AuditLog.user_id == user_id)
    return (await session.execute(stmt)).scalars().all()
