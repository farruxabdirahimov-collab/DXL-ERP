"""Joriy foydalanuvchi haqida ma'lumot."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.db import get_session
from app.models import ROLE_LABELS_UZ, Doctor, Role, User
from app.permissions import effective_permissions
from app.schemas import MeOut

router = APIRouter(tags=["me"])


@router.get("/me", response_model=MeOut)
async def read_me(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> MeOut:
    doctor_id = None
    if user.role is Role.DOCTOR:
        doctor_id = (
            await session.execute(select(Doctor.id).where(Doctor.user_id == user.id))
        ).scalar_one_or_none()

    return MeOut(
        id=user.id,
        telegram_id=user.telegram_id,
        full_name=user.full_name,
        phone=user.phone,
        role=user.role,
        role_label=ROLE_LABELS_UZ[user.role],
        is_active=user.is_active,
        has_own_stock=user.has_own_stock,
        extra_roles=list(user.extra_roles or []),
        permissions=sorted(effective_permissions(user)),
        doctor_id=doctor_id,
    )
