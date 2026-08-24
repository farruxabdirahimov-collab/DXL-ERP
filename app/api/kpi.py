"""Menejer KPI: ish haqi hisobi va post/otziv tasdiqlash."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_perm
from app.db import get_session
from app.models import (
    SUBMISSION_KIND_UZ,
    SUBMISSION_STATUS_UZ,
    ContentSubmission,
    Role,
    SubmissionKind,
    SubmissionStatus,
    User,
    utcnow,
)
from app.permissions import PLANS_EDIT, PLANS_VIEW, user_can
from app.schemas import OkOut, SubmissionIn, SubmissionReviewIn
from app.services import kpi as kpi_service
from app.services.fx import today_local
from app.utils.audit import log_action

router = APIRouter(prefix="/kpi", tags=["kpi"])


def _out(row: ContentSubmission, agent_name: str | None = None) -> dict:
    return {
        "id": row.id,
        "agent_id": row.agent_id,
        "agent_name": agent_name,
        "kind": row.kind.value,
        "kind_label": SUBMISSION_KIND_UZ[row.kind],
        "url": row.url,
        "note": row.note,
        "status": row.status.value,
        "status_label": SUBMISSION_STATUS_UZ[row.status],
        "period": f"{row.period_month:02d}.{row.period_year}",
        "created_at": row.created_at.isoformat(),
        "reject_reason": row.reject_reason,
    }


# --------------------------------------------------------------- ish haqi
@router.get("/my-salary")
async def my_salary(
    year: int | None = None,
    month: int | None = None,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_perm(PLANS_VIEW)),
):
    """Menejerning kutilayotgan oyligi — oy davomida jonli yangilanadi."""
    return await kpi_service.salary(session, user, year, month)


@router.get("/salaries")
async def all_salaries(
    year: int | None = None,
    month: int | None = None,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_perm(PLANS_EDIT)),
):
    """Direktor uchun: barcha menejerlar oyligi bitta jadvalda."""
    rows = await kpi_service.all_salaries(session, year, month)
    return {
        "rows": rows,
        "total_usd": sum((r["total_usd"] for r in rows), start=0),
    }


# ------------------------------------------------------- post va otziv
@router.get("/submissions")
async def list_submissions(
    status: SubmissionStatus | None = None,
    agent_id: int | None = None,
    limit: int = Query(default=100, le=300),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_perm(PLANS_VIEW)),
):
    stmt = (
        select(ContentSubmission)
        .order_by(ContentSubmission.id.desc())
        .limit(limit)
    )
    # Menejer faqat o'zinikini ko'radi
    if not user_can(user, PLANS_EDIT):
        stmt = stmt.where(ContentSubmission.agent_id == user.id)
    elif agent_id is not None:
        stmt = stmt.where(ContentSubmission.agent_id == agent_id)
    if status is not None:
        stmt = stmt.where(ContentSubmission.status == status)

    rows = (await session.execute(stmt)).scalars().all()
    ismlar = {
        u.id: u.full_name
        for u in (
            await session.execute(
                select(User).where(User.id.in_([r.agent_id for r in rows] or [0]))
            )
        ).scalars().all()
    }
    return [_out(r, ismlar.get(r.agent_id)) for r in rows]


@router.post("/submissions", response_model=OkOut, status_code=201)
async def create_submission(
    payload: SubmissionIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_perm(PLANS_VIEW)),
):
    """Menejer havola tashlaydi. Direktor tasdiqlagach ish haqqa kiradi."""
    try:
        kind = SubmissionKind(payload.kind)
    except ValueError:
        raise HTTPException(400, f"Noma'lum tur: {payload.kind}") from None

    today = today_local()
    row = ContentSubmission(
        agent_id=user.id,
        kind=kind,
        url=payload.url.strip(),
        note=payload.note,
        # Qaysi oyga hisoblanishi joylangan sana bo'yicha — direktor kech
        # tasdiqlasa ham oy o'zgarmaydi
        period_year=today.year,
        period_month=today.month,
    )
    session.add(row)
    await session.flush()
    await log_action(
        session, user, "submit", "kpi", row.id,
        new={"kind": kind.value, "url": row.url},
    )
    return OkOut(
        ok=True,
        message=f"{SUBMISSION_KIND_UZ[kind]} yuborildi — direktor tasdig'ini kuting",
    )


@router.post("/submissions/{submission_id}/review", response_model=OkOut)
async def review_submission(
    submission_id: int,
    payload: SubmissionReviewIn,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(require_perm(PLANS_EDIT)),
):
    """Direktor tasdiqlaydi yoki rad etadi."""
    row = await session.get(ContentSubmission, submission_id)
    if row is None:
        raise HTTPException(404, "Yozuv topilmadi")

    row.status = (
        SubmissionStatus.APPROVED if payload.approve else SubmissionStatus.REJECTED
    )
    row.reviewed_by_id = actor.id
    row.reviewed_at = utcnow()
    row.reject_reason = None if payload.approve else payload.reason
    await session.flush()

    await log_action(
        session, actor, "review", "kpi", submission_id,
        new={"status": row.status.value, "reason": row.reject_reason},
    )

    # Menejerga darhol xabar — oyligi o'zgargani bilinsin
    from app.bot import notify

    holat = "hisobga olindi ✅" if payload.approve else "rad etildi ❌"
    sabab = f"\nSabab: {payload.reason}" if row.reject_reason else ""
    await notify.send_to_user_id(
        session,
        row.agent_id,
        f"{SUBMISSION_KIND_UZ[row.kind]} {holat}{sabab}",
        kind="kpi_review",
    )

    return OkOut(ok=True, message=f"Yozuv {holat}")


@router.delete("/submissions/{submission_id}", response_model=OkOut)
async def delete_submission(
    submission_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_perm(PLANS_VIEW)),
):
    """Menejer o'zining tasdiqlanmagan yozuvini o'chira oladi."""
    row = await session.get(ContentSubmission, submission_id)
    if row is None:
        raise HTTPException(404, "Yozuv topilmadi")
    if row.agent_id != user.id and not user_can(user, PLANS_EDIT):
        raise HTTPException(403, "Bu yozuv sizniki emas")
    if row.status is SubmissionStatus.APPROVED and not user_can(user, PLANS_EDIT):
        raise HTTPException(400, "Tasdiqlangan yozuvni o'chira olmaysiz")

    await session.delete(row)
    await log_action(session, user, "delete", "kpi", submission_id)
    return OkOut(ok=True, message="O'chirildi")
