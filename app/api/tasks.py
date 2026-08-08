"""Agent vazifalari: tug'ilgan kun, uxlagan mijoz, qarz undirish."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.db import get_session
from app.models import TASK_LABELS_UZ, Doctor, Role, Task, TaskKind, TaskStatus, User, utcnow
from app.schemas import TaskCreateIn, TaskOut, TaskUpdateIn
from app.services.fx import today_local

router = APIRouter(prefix="/tasks", tags=["tasks"])


async def _to_out(session: AsyncSession, task: Task) -> TaskOut:
    out = TaskOut.model_validate(task)
    out.kind_label = TASK_LABELS_UZ.get(task.kind)
    if task.doctor_id:
        doctor = await session.get(Doctor, task.doctor_id)
        if doctor:
            out.doctor_name = doctor.full_name
            out.doctor_phone = doctor.phone
    return out


@router.get("", response_model=list[TaskOut])
async def list_tasks(
    status: TaskStatus | None = TaskStatus.OPEN,
    until: date | None = None,
    user_id: int | None = None,
    limit: int = Query(default=100, le=300),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Mening vazifalarim (rahbariyat boshqa xodimnikini ham ko'ra oladi)."""
    stmt = select(Task).order_by(Task.due_date, Task.id).limit(limit)

    target_id = user.id
    if user_id is not None and user.role in (Role.DIRECTOR, Role.SUPERADMIN, Role.FOUNDER):
        target_id = user_id
    stmt = stmt.where(Task.user_id == target_id)

    if status is not None:
        stmt = stmt.where(Task.status == status)
    stmt = stmt.where(Task.due_date <= (until or today_local()))

    rows = (await session.execute(stmt)).scalars().all()
    return [await _to_out(session, task) for task in rows]


@router.post("", response_model=TaskOut, status_code=201)
async def create_task(
    payload: TaskCreateIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    target_id = payload.user_id or user.id
    if target_id != user.id and user.role not in (Role.DIRECTOR, Role.SUPERADMIN):
        raise HTTPException(403, "Boshqa xodimga vazifa qo'yishga ruxsat yo'q")

    task = Task(
        created_at=utcnow(),
        user_id=target_id,
        doctor_id=payload.doctor_id,
        kind=TaskKind.MANUAL,
        due_date=payload.due_date,
        title=payload.title,
        note=payload.note,
        status=TaskStatus.OPEN,
    )
    session.add(task)
    await session.flush()
    return await _to_out(session, task)


@router.patch("/{task_id}", response_model=TaskOut)
async def update_task(
    task_id: int,
    payload: TaskUpdateIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    task = await session.get(Task, task_id)
    if task is None:
        raise HTTPException(404, "Vazifa topilmadi")
    if task.user_id != user.id and user.role not in (Role.DIRECTOR, Role.SUPERADMIN):
        raise HTTPException(403, "Bu vazifa sizga tegishli emas")

    task.status = payload.status
    if payload.note is not None:
        task.note = payload.note
    if payload.status is not TaskStatus.OPEN:
        task.done_at = utcnow()
    await session.flush()
    return await _to_out(session, task)
