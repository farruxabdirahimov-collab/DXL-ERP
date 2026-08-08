"""Agent tashriflari — geolokatsiya bilan qayd etish."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user, require_perm
from app.db import get_session
from app.models import Doctor, Role, User, Visit, utcnow
from app.permissions import VISITS_ALL, VISITS_OWN, can
from app.schemas import VisitIn, VisitOut
from app.services.reports import day_bounds
from app.services.settings_service import get_setting
from app.utils.geo import haversine_m

router = APIRouter(prefix="/visits", tags=["visits"])


@router.post("", response_model=VisitOut, status_code=201)
async def check_in(
    payload: VisitIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Klinikaga kelganda «tashrif» tugmasi — joylashuv va vaqt yoziladi."""
    if not (can(user.role, VISITS_OWN) or can(user.role, VISITS_ALL)):
        raise HTTPException(403, "Tashrif qayd etishga ruxsat yo'q")

    doctor = await session.get(Doctor, payload.doctor_id)
    if doctor is None:
        raise HTTPException(404, "Vrach topilmadi")
    if user.role is Role.AGENT and doctor.agent_id != user.id:
        raise HTTPException(403, "Bu vrach sizga biriktirilmagan")

    distance = None
    if payload.lat is not None and payload.lon is not None and doctor.lat and doctor.lon:
        distance = round(
            haversine_m(payload.lat, payload.lon, doctor.lat, doctor.lon), 1
        )

    visit = Visit(
        created_at=utcnow(),
        agent_id=user.id,
        doctor_id=doctor.id,
        lat=payload.lat,
        lon=payload.lon,
        distance_m=distance,
        result=payload.result,
        order_id=payload.order_id,
        note=payload.note,
    )
    session.add(visit)
    await session.flush()

    out = VisitOut.model_validate(visit)
    out.agent_name = user.full_name
    out.doctor_name = doctor.full_name
    return out


@router.get("", response_model=list[VisitOut])
async def list_visits(
    agent_id: int | None = None,
    doctor_id: int | None = None,
    on_date: date | None = None,
    limit: int = Query(default=100, le=500),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    if not (can(user.role, VISITS_OWN) or can(user.role, VISITS_ALL)):
        raise HTTPException(403, "Ruxsat yo'q")

    stmt = select(Visit).order_by(Visit.created_at.desc()).limit(limit)
    if not can(user.role, VISITS_ALL):
        stmt = stmt.where(Visit.agent_id == user.id)
    elif agent_id is not None:
        stmt = stmt.where(Visit.agent_id == agent_id)
    if doctor_id is not None:
        stmt = stmt.where(Visit.doctor_id == doctor_id)
    if on_date is not None:
        start, end = day_bounds(on_date)
        stmt = stmt.where(Visit.created_at >= start, Visit.created_at <= end)

    rows = (await session.execute(stmt)).scalars().all()
    result = []
    for visit in rows:
        out = VisitOut.model_validate(visit)
        agent = await session.get(User, visit.agent_id)
        doctor = await session.get(Doctor, visit.doctor_id)
        out.agent_name = agent.full_name if agent else None
        out.doctor_name = doctor.full_name if doctor else None
        result.append(out)
    return result


@router.get("/today-summary")
async def today_summary(
    on_date: date | None = None,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Direktor uchun: bugun kim nechta tashrif qildi va qaysilari 'joyida' edi."""
    if not can(user.role, VISITS_ALL):
        raise HTTPException(403, "Ruxsat yo'q")

    from app.services.fx import today_local

    day = on_date or today_local()
    start, end = day_bounds(day)
    max_distance = float(await get_setting(session, "visit_max_distance_m") or 300)

    rows = (
        await session.execute(
            select(Visit).where(Visit.created_at >= start, Visit.created_at <= end)
        )
    ).scalars().all()

    by_agent: dict[int, dict] = {}
    for visit in rows:
        entry = by_agent.setdefault(
            visit.agent_id, {"visits": 0, "on_site": 0, "far": 0, "unknown": 0}
        )
        entry["visits"] += 1
        if visit.distance_m is None:
            entry["unknown"] += 1
        elif visit.distance_m <= max_distance:
            entry["on_site"] += 1
        else:
            entry["far"] += 1

    result = []
    for agent_id, stats in by_agent.items():
        agent = await session.get(User, agent_id)
        result.append(
            {"agent_id": agent_id, "full_name": agent.full_name if agent else "—", **stats}
        )
    result.sort(key=lambda r: r["visits"], reverse=True)
    return {"date": day.isoformat(), "max_distance_m": max_distance, "agents": result}
