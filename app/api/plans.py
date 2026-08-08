"""Oylik reja va uning bajarilishi."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_perm
from app.db import get_session
from app.models import Role, User
from app.permissions import PLANS_EDIT, PLANS_VIEW
from app.schemas import OkOut, PlanIn
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


@router.get("/{user_id}")
async def user_plan(
    user_id: int,
    year: int | None = None,
    month: int | None = None,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(require_perm(PLANS_VIEW)),
):
    if actor.role is Role.AGENT and actor.id != user_id:
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
