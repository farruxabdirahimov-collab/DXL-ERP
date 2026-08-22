"""Oylik reja va uning bajarilishi."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_perm
from app.db import get_session
from app.models import Role, User
from app.permissions import PLANS_EDIT, PLANS_VIEW, user_can
from app.schemas import BulkPlanIn, CompanyPlanIn, OkOut, PlanIn
from app.services import plans as plans_service
from app.services.fx import today_local
from app.utils.audit import log_action

router = APIRouter(prefix="/plans", tags=["plans"])


@router.get("/my")
async def my_plan(
    year: int | None = None,
    month: int | None = None,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_perm(PLANS_VIEW)),
):
    """Agentning o'z rejasi va bajarilishi (3 ko'rsatkich bo'yicha)."""
    progress = await plans_service.progress(session, user, year, month)
    data = progress.to_dict()
    data["expected_pace_pct"] = plans_service.expected_pace_pct(
        progress.days_passed, progress.days_in_month
    )
    # «Shu sur'atda oy oxirida qancha bo'ladi va kuniga qancha kerak»
    data["forecast"] = asdict(
        plans_service.forecast(
            progress.amount.fact,
            progress.amount.target,
            progress.days_passed,
            progress.days_in_month,
        )
    )
    return data


@router.get("/leaderboard")
async def leaderboard(
    year: int | None = None,
    month: int | None = None,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_perm(PLANS_VIEW)),
):
    """Agentlar reytingi. Agent o'zini va o'rnini ko'radi."""
    rows = await plans_service.leaderboard(session, year, month)
    return [
        {**row.to_dict(), "rank": index + 1} for index, row in enumerate(rows)
    ]


# Diqqat: bu yo'llar `/{user_id}` dan OLDIN e'lon qilinadi, aks holda
# FastAPI «company» va «history» ni user_id deb o'qiydi.
@router.get("/company")
async def company_plan(
    year: int | None = None,
    month: int | None = None,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_perm(PLANS_EDIT)),
):
    """Kompaniya rejasi, prognoz va agentlarga taqsimot nazorati."""
    return await plans_service.company_progress(session, year, month)


@router.post("/company", response_model=OkOut)
async def set_company_plan(
    payload: CompanyPlanIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_perm(PLANS_EDIT)),
):
    await plans_service.upsert_company_plan(
        session,
        year=payload.year,
        month=payload.month,
        actor=user,
        target_amount_usd=payload.target_amount_usd,
        target_units=payload.target_units,
        target_collection_usd=payload.target_collection_usd,
        target_new_doctors=payload.target_new_doctors,
        note=payload.note,
    )
    await log_action(
        session, user, "set_company_plan", "plan",
        f"{payload.year}-{payload.month:02d}", new=payload.model_dump(mode="json"),
    )
    return OkOut(
        ok=True,
        message=f"{payload.month}/{payload.year} kompaniya rejasi saqlandi",
    )


@router.get("/history")
async def plan_history(
    user_id: int | None = None,
    months: int = Query(default=6, ge=2, le=24),
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(require_perm(PLANS_VIEW)),
):
    """Oxirgi oylar bajarilishi — grafik uchun."""
    target = actor
    if user_id is not None and user_id != actor.id:
        if not user_can(actor, PLANS_EDIT):
            raise HTTPException(403, "Faqat o'z tarixingizni ko'ra olasiz")
        found = await session.get(User, user_id)
        if found is None:
            raise HTTPException(404, "Xodim topilmadi")
        target = found
    return await plans_service.history(session, target, months)


@router.post("/copy-previous", response_model=OkOut)
async def copy_previous(
    year: int,
    month: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_perm(PLANS_EDIT)),
):
    """O'tgan oy rejalarini shu oyga nusxalaydi — reja qo'yish bir bosishda."""
    count = await plans_service.copy_from_previous(
        session, year=year, month=month, actor=user
    )
    await log_action(
        session, user, "copy_plans", "plan", f"{year}-{month:02d}",
        new={"nusxalandi": count},
    )
    return OkOut(
        ok=True,
        message=(
            f"{count} ta agentga o'tgan oy rejasi nusxalandi"
            if count
            else "Nusxalanadigan reja topilmadi (o'tgan oyda reja yo'q yoki hammasi qo'yilgan)"
        ),
    )


@router.post("/bulk", response_model=OkOut)
async def bulk_plan(
    payload: BulkPlanIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_perm(PLANS_EDIT)),
):
    """Barcha faol agentlarga bir xil reja qo'yadi."""
    count = await plans_service.apply_to_all_agents(
        session,
        year=payload.year,
        month=payload.month,
        actor=user,
        target_amount_usd=payload.target_amount_usd,
        target_units=payload.target_units,
        target_collection_usd=payload.target_collection_usd,
        target_new_doctors=payload.target_new_doctors,
        target_active_doctors=payload.target_active_doctors,
        target_visits=payload.target_visits,
    )
    await log_action(
        session, user, "bulk_plan", "plan", f"{payload.year}-{payload.month:02d}",
        new=payload.model_dump(mode="json"),
    )
    return OkOut(ok=True, message=f"{count} ta agentga reja qo'yildi")


@router.get("/{user_id}")
async def user_plan(
    user_id: int,
    year: int | None = None,
    month: int | None = None,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(require_perm(PLANS_VIEW)),
):
    if not user_can(actor, PLANS_EDIT) and actor.id != user_id:
        raise HTTPException(403, "Faqat o'z rejangizni ko'ra olasiz")
    agent = await session.get(User, user_id)
    if agent is None:
        raise HTTPException(404, "Xodim topilmadi")
    progress = await plans_service.progress(session, agent, year, month)
    return progress.to_dict()


@router.post("", response_model=OkOut)
async def set_plan(
    payload: PlanIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_perm(PLANS_EDIT)),
):
    agent = await session.get(User, payload.user_id)
    if agent is None or agent.role is not Role.AGENT:
        raise HTTPException(404, "Sotuv agenti topilmadi")

    await plans_service.upsert_plan(
        session,
        user_id=payload.user_id,
        year=payload.year,
        month=payload.month,
        target_amount_usd=payload.target_amount_usd,
        target_units=payload.target_units,
        target_collection_usd=payload.target_collection_usd,
        target_new_doctors=payload.target_new_doctors,
        target_active_doctors=payload.target_active_doctors,
        target_visits=payload.target_visits,
        actor=user,
    )
    await log_action(
        session, user, "set_plan", "user", payload.user_id, new=payload.model_dump()
    )
    return OkOut(
        ok=True,
        message=f"{agent.full_name} uchun {payload.month}/{payload.year} rejasi saqlandi",
    )


@router.get("")
async def all_plans(
    year: int | None = None,
    month: int | None = None,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_perm(PLANS_EDIT)),
):
    """Direktor uchun: barcha agentlar rejasi bitta jadvalda."""
    today = today_local()
    year = year or today.year
    month = month or today.month
    agents = (
        await session.execute(
            select(User).where(User.role == Role.AGENT, User.is_active.is_(True))
            .order_by(User.full_name)
        )
    ).scalars().all()

    result = []
    for agent in agents:
        plan = await plans_service.get_plan(session, agent.id, year, month)
        progress = await plans_service.progress(session, agent, year, month)
        result.append(
            {
                "user_id": agent.id,
                "full_name": agent.full_name,
                "target_amount_usd": plan.target_amount_usd if plan else 0,
                "target_units": plan.target_units if plan else 0,
                "target_collection_usd": plan.target_collection_usd if plan else 0,
                **progress.to_dict(),
            }
        )
    return result
