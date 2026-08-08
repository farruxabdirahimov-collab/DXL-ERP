"""Vrachlar (mijozlar) — kartochka, qidiruv, qarz, tug'ilgan kunlar."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user, require_perm
from app.db import get_session
from app.models import Doctor, Order, OrderStatus, Role, User
from app.permissions import DOCTORS_ALL, DOCTORS_EDIT, DOCTORS_VIEW, can
from app.schemas import DoctorIn, DoctorOut, DoctorUpdateIn, OkOut
from app.services import debt as debt_service
from app.services.fx import today_local
from app.services.loyalty import upcoming_birthdays_filter
from app.services.settings_service import get_setting
from app.utils.audit import log_action

router = APIRouter(prefix="/doctors", tags=["doctors"])


def _scope(stmt, user: User):
    """Agent faqat o'ziga biriktirilgan vrachlarni ko'radi."""
    if user.role is Role.AGENT and not can(user.role, DOCTORS_ALL):
        return stmt.where(Doctor.agent_id == user.id)
    return stmt


async def _to_out(session: AsyncSession, doctor: Doctor) -> DoctorOut:
    out = DoctorOut.model_validate(doctor)
    if doctor.agent_id:
        agent = await session.get(User, doctor.agent_id)
        out.agent_name = agent.full_name if agent else None
    summary = await debt_service.doctor_debt(session, doctor.id)
    out.debt_usd = summary.total_usd
    out.overdue_usd = summary.overdue_usd
    out.oldest_due_date = summary.oldest_due_date
    out.overdue_days = summary.max_overdue_days
    return out


@router.get("", response_model=list[DoctorOut])
async def list_doctors(
    search: str | None = None,
    agent_id: int | None = None,
    category: str | None = None,
    only_debtors: bool = False,
    only_overdue: bool = False,
    limit: int = Query(default=200, le=1000),
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_perm(DOCTORS_VIEW)),
):
    stmt = select(Doctor).where(Doctor.is_active.is_(True))
    stmt = _scope(stmt, user)
    if agent_id and can(user.role, DOCTORS_ALL):
        stmt = stmt.where(Doctor.agent_id == agent_id)
    if category:
        stmt = stmt.where(Doctor.category == category)
    if search:
        pattern = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                Doctor.full_name.ilike(pattern),
                Doctor.clinic_name.ilike(pattern),
                Doctor.phone.ilike(pattern),
            )
        )
    rows = (
        await session.execute(stmt.order_by(Doctor.full_name).limit(limit).offset(offset))
    ).scalars().all()

    result = [await _to_out(session, doctor) for doctor in rows]
    if only_overdue:
        result = [r for r in result if r.overdue_usd > 0]
    elif only_debtors:
        result = [r for r in result if r.debt_usd > 0]
    return result


@router.get("/birthdays", response_model=list[DoctorOut])
async def birthdays(
    days: int = Query(default=7, ge=0, le=60),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_perm(DOCTORS_VIEW)),
):
    """Yaqin kunlarda tug'ilgan kuni bo'lgan vrachlar."""
    stmt = _scope(
        select(Doctor).where(Doctor.is_active.is_(True), Doctor.birth_date.is_not(None)),
        user,
    )
    doctors = (await session.execute(stmt)).scalars().all()
    upcoming = upcoming_birthdays_filter(list(doctors), today_local(), days)
    return [await _to_out(session, doctor) for doctor in upcoming]


@router.get("/sleeping", response_model=list[DoctorOut])
async def sleeping(
    days: int | None = None,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_perm(DOCTORS_VIEW)),
):
    """Uzoq vaqt xarid qilmagan mijozlar."""
    days = days or int(await get_setting(session, "sleeping_client_days") or 60)
    cutoff = today_local() - timedelta(days=days)
    stmt = _scope(
        select(Doctor).where(
            Doctor.is_active.is_(True),
            or_(Doctor.last_order_at.is_(None), Doctor.last_order_at < cutoff),
        ),
        user,
    )
    rows = (
        await session.execute(stmt.order_by(Doctor.last_order_at.asc().nullsfirst()))
    ).scalars().all()
    return [await _to_out(session, doctor) for doctor in rows]


@router.get("/{doctor_id}", response_model=DoctorOut)
async def get_doctor(
    doctor_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_perm(DOCTORS_VIEW)),
):
    doctor = await session.get(Doctor, doctor_id)
    if doctor is None:
        raise HTTPException(404, "Vrach topilmadi")
    if user.role is Role.AGENT and doctor.agent_id != user.id:
        raise HTTPException(403, "Bu vrach sizga biriktirilmagan")
    return await _to_out(session, doctor)


@router.get("/{doctor_id}/debt")
async def doctor_debt(
    doctor_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_perm(DOCTORS_VIEW)),
):
    """Vrachning qarzi: buyurtmalar kesimida muddat va kechikish bilan."""
    doctor = await session.get(Doctor, doctor_id)
    if doctor is None:
        raise HTTPException(404, "Vrach topilmadi")
    if user.role is Role.AGENT and doctor.agent_id != user.id:
        raise HTTPException(403, "Bu vrach sizga biriktirilmagan")

    summary = await debt_service.doctor_debt(session, doctor_id)
    orders = (
        await session.execute(debt_service.unpaid_orders_stmt(doctor_id))
    ).scalars().all()
    today = today_local()

    return {
        "doctor_id": doctor_id,
        "full_name": doctor.full_name,
        "debt_limit_usd": doctor.debt_limit_usd,
        "payment_term_days": doctor.payment_term_days,
        "total_usd": summary.total_usd,
        "overdue_usd": summary.overdue_usd,
        "not_due_usd": summary.not_due_usd,
        "max_overdue_days": summary.max_overdue_days,
        "buckets": summary.buckets,
        "orders": [
            {
                "id": o.id,
                "number": o.number,
                "delivered_at": o.delivered_at.isoformat() if o.delivered_at else None,
                "due_date": o.due_date.isoformat() if o.due_date else None,
                "total_usd": o.total_usd,
                "paid_usd": o.paid_usd,
                "debt_usd": o.debt_usd,
                "overdue_days": (today - o.due_date).days
                if o.due_date and o.due_date < today
                else 0,
            }
            for o in orders
        ],
    }


@router.post("", response_model=DoctorOut, status_code=201)
async def create_doctor(
    payload: DoctorIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_perm(DOCTORS_EDIT)),
):
    exists = (
        await session.execute(select(Doctor).where(Doctor.phone == payload.phone))
    ).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(409, f"Bu telefon raqam bilan vrach bor: {exists.full_name}")

    data = payload.model_dump()
    if data.get("payment_term_days") is None:
        data["payment_term_days"] = int(
            await get_setting(session, "default_payment_term_days") or 30
        )
    if data.get("debt_limit_usd") is None:
        data["debt_limit_usd"] = Decimal(
            str(await get_setting(session, "default_debt_limit_usd") or 0)
        )
    if user.role is Role.AGENT:
        data["agent_id"] = user.id

    doctor = Doctor(**data, created_by_id=user.id)
    session.add(doctor)
    await session.flush()
    await log_action(session, user, "create", "doctor", doctor.id, new=data)
    return await _to_out(session, doctor)


@router.patch("/{doctor_id}", response_model=DoctorOut)
async def update_doctor(
    doctor_id: int,
    payload: DoctorUpdateIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_perm(DOCTORS_EDIT)),
):
    doctor = await session.get(Doctor, doctor_id)
    if doctor is None:
        raise HTTPException(404, "Vrach topilmadi")
    if user.role is Role.AGENT and doctor.agent_id != user.id:
        raise HTTPException(403, "Bu vrach sizga biriktirilmagan")

    changes = payload.model_dump(exclude_unset=True, exclude_none=True)
    # Moliyaviy shartlarni faqat rahbariyat/buxgalter o'zgartira oladi
    financial = {"debt_limit_usd", "payment_term_days", "discount_pct", "credit_block_override"}
    if user.role is Role.AGENT:
        for key in financial:
            changes.pop(key, None)
        changes.pop("agent_id", None)

    old = {key: getattr(doctor, key) for key in changes}
    for key, value in changes.items():
        setattr(doctor, key, value)
    await session.flush()
    await log_action(session, user, "update", "doctor", doctor_id, old=old, new=changes)
    return await _to_out(session, doctor)


@router.delete("/{doctor_id}", response_model=OkOut)
async def deactivate_doctor(
    doctor_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_perm(DOCTORS_EDIT)),
):
    doctor = await session.get(Doctor, doctor_id)
    if doctor is None:
        raise HTTPException(404, "Vrach topilmadi")

    open_orders = (
        await session.execute(
            select(Order).where(
                Order.doctor_id == doctor_id,
                Order.status.in_([OrderStatus.NEW, OrderStatus.APPROVED, OrderStatus.PICKING]),
            )
        )
    ).scalars().first()
    if open_orders is not None:
        raise HTTPException(400, "Bu vrachda ochiq buyurtma bor, avval yakunlang")

    doctor.is_active = False
    await session.flush()
    await log_action(session, user, "deactivate", "doctor", doctor_id)
    return OkOut(ok=True, message="Vrach arxivga o'tkazildi")
