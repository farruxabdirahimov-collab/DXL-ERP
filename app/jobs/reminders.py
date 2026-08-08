"""Ertalabki eslatmalar, oylik yakun va kechki qayta hisob."""

from __future__ import annotations

import logging
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import notify
from app.db import session_scope
from app.models import (
    Doctor,
    Role,
    Task,
    TaskKind,
    TaskStatus,
    User,
    utcnow,
)
from app.services import plans as plans_service, reports as rp
from app.services.debt import overdue_orders, total_debt
from app.services.fx import today_local
from app.services.loyalty import recalculate, upcoming_birthdays_filter
from app.services.settings_service import get_setting
from app.utils.fmt import (
    as_aware,
    bullet_list,
    fmt_date,
    fmt_short_date,
    money_usd,
    plan_emoji,
)

log = logging.getLogger(__name__)


async def _ensure_task(
    session: AsyncSession,
    *,
    user_id: int,
    doctor_id: int | None,
    kind: TaskKind,
    due_date: date,
    title: str,
    dedup_key: str,
) -> bool:
    """Vazifani takrorlamasdan yaratadi. Yangi yaratilgan bo'lsa True."""
    exists = (
        await session.execute(select(Task.id).where(Task.dedup_key == dedup_key))
    ).scalar_one_or_none()
    if exists is not None:
        return False
    session.add(
        Task(
            created_at=utcnow(),
            user_id=user_id,
            doctor_id=doctor_id,
            kind=kind,
            due_date=due_date,
            title=title,
            status=TaskStatus.OPEN,
            dedup_key=dedup_key,
        )
    )
    await session.flush()
    return True


async def birthday_reminders(session: AsyncSession, day: date) -> int:
    """Tug'ilgan kuni yaqinlashgan vrachlar — agentiga vazifa va xabar."""
    notice_days = int(await get_setting(session, "birthday_notice_days") or 3)
    doctors = (
        await session.execute(
            select(Doctor).where(
                Doctor.is_active.is_(True), Doctor.birth_date.is_not(None)
            )
        )
    ).scalars().all()

    upcoming = upcoming_birthdays_filter(list(doctors), day, notice_days)
    by_agent: dict[int, list[str]] = {}
    created = 0

    for doctor in upcoming:
        assert doctor.birth_date is not None
        this_year = doctor.birth_date.replace(year=day.year)
        if this_year < day:
            this_year = doctor.birth_date.replace(year=day.year + 1)
        when = "bugun" if this_year == day else fmt_short_date(this_year)

        target_id = doctor.agent_id
        if target_id is None:
            continue
        title = f"🎂 {doctor.full_name} — tug'ilgan kun ({when})"
        if await _ensure_task(
            session,
            user_id=target_id,
            doctor_id=doctor.id,
            kind=TaskKind.BIRTHDAY,
            due_date=this_year,
            title=title,
            dedup_key=f"birthday:{doctor.id}:{this_year.isoformat()}",
        ):
            created += 1
        by_agent.setdefault(target_id, []).append(
            f"{doctor.full_name} ({doctor.clinic_name or '—'}) — {when}, tel: {doctor.phone}"
        )

    for agent_id, items in by_agent.items():
        await notify.send_to_user_id(
            session,
            agent_id,
            "🎂 <b>Yaqin kunlardagi tug'ilgan kunlar</b>\n" + bullet_list(items, limit=10),
            kind="birthday",
            dedup_key=f"birthday_digest:{agent_id}:{day.isoformat()}",
            button=("Vrachlarni ochish", "/doctors"),
        )

    return created


async def overdue_reminders(session: AsyncSession, day: date) -> int:
    """Muddati o'tgan qarzlar — agent, buxgalter va direktorga."""
    orders = await overdue_orders(session, day)
    if not orders:
        return 0

    by_agent: dict[int, list[str]] = {}
    created = 0
    for order in orders:
        doctor = await session.get(Doctor, order.doctor_id)
        if doctor is None:
            continue
        days_late = (day - order.due_date).days if order.due_date else 0
        line = (
            f"{doctor.full_name} — {money_usd(order.debt_usd)}, "
            f"{days_late} kun kechikdi ({order.number})"
        )
        if order.agent_id:
            by_agent.setdefault(order.agent_id, []).append(line)
            if await _ensure_task(
                session,
                user_id=order.agent_id,
                doctor_id=doctor.id,
                kind=TaskKind.OVERDUE,
                due_date=day,
                title=f"💳 {doctor.full_name} — qarz {money_usd(order.debt_usd)} ({days_late} kun)",
                dedup_key=f"overdue:{order.id}:{day.isoformat()}",
            ):
                created += 1

    for agent_id, items in by_agent.items():
        await notify.send_to_user_id(
            session,
            agent_id,
            "⏰ <b>Muddati o'tgan qarzlar</b>\n" + bullet_list(items, limit=10),
            kind="overdue",
            dedup_key=f"overdue_digest:{agent_id}:{day.isoformat()}",
            button=("Qarzlarni ochish", "/debts"),
        )

    debt = await total_debt(session, day)
    all_items = []
    for order in orders[:10]:
        doctor = await session.get(Doctor, order.doctor_id)
        all_items.append(
            f"{doctor.full_name if doctor else '—'} — {money_usd(order.debt_usd)} "
            f"({(day - order.due_date).days} kun)"
        )
    await notify.send_to_roles(
        session,
        [Role.ACCOUNTANT, Role.DIRECTOR],
        f"⏰ <b>Muddati o'tgan qarz: {money_usd(debt['overdue_usd'])}</b>\n"
        f"{len(orders)} ta buyurtma bo'yicha\n\n" + bullet_list(all_items, limit=10),
        kind="overdue_management",
        dedup_key=f"overdue_management:{day.isoformat()}",
        button=("Qarzlarni ochish", "/debts"),
    )
    return created


async def sleeping_reminders(session: AsyncSession, day: date) -> int:
    """Uzoq vaqt xarid qilmagan mijozlar — agentga qo'ng'iroq vazifasi."""
    days = int(await get_setting(session, "sleeping_client_days") or 60)
    cutoff = utcnow() - timedelta(days=days)

    doctors = (
        await session.execute(
            select(Doctor).where(
                Doctor.is_active.is_(True),
                Doctor.agent_id.is_not(None),
                Doctor.last_order_at.is_not(None),
                Doctor.last_order_at < cutoff,
            )
        )
    ).scalars().all()
    if not doctors:
        return 0

    by_agent: dict[int, list[str]] = {}
    created = 0
    # Haftada bir marta eslatamiz (dushanba)
    week_key = f"{day.isocalendar().year}-W{day.isocalendar().week}"

    for doctor in doctors:
        assert doctor.agent_id is not None
        last_order = as_aware(doctor.last_order_at)
        idle_days = (utcnow() - last_order).days if last_order else 0
        if await _ensure_task(
            session,
            user_id=doctor.agent_id,
            doctor_id=doctor.id,
            kind=TaskKind.SLEEPING,
            due_date=day,
            title=f"📞 {doctor.full_name} — {idle_days} kundan beri xarid yo'q",
            dedup_key=f"sleeping:{doctor.id}:{week_key}",
        ):
            created += 1
            by_agent.setdefault(doctor.agent_id, []).append(
                f"{doctor.full_name} — {idle_days} kun, tel: {doctor.phone}"
            )

    for agent_id, items in by_agent.items():
        await notify.send_to_user_id(
            session,
            agent_id,
            f"😴 <b>Uzoq vaqt xarid qilmagan mijozlar</b> ({days}+ kun)\n"
            + bullet_list(items, limit=10),
            kind="sleeping",
            dedup_key=f"sleeping_digest:{agent_id}:{week_key}",
            button=("Vrachlarni ochish", "/doctors"),
        )
    return created


async def run_morning_reminders(day: date | None = None) -> None:
    """Har kuni ertalab (09:00) ishlaydigan job."""
    day = day or today_local()
    async with session_scope() as session:
        birthdays = await birthday_reminders(session, day)
        overdue = await overdue_reminders(session, day)
        sleeping = 0
        if day.weekday() == 0:  # faqat dushanba kunlari
            sleeping = await sleeping_reminders(session, day)
    log.info(
        "Ertalabki eslatmalar: tug'ilgan kun=%s, qarz=%s, uxlagan=%s",
        birthdays, overdue, sleeping,
    )


async def run_nightly_recalc(day: date | None = None) -> None:
    """Kechasi (02:00): vrach toifalari va sodiqlik ko'rsatkichini qayta hisoblash."""
    day = day or today_local()
    async with session_scope() as session:
        updated = await recalculate(session, day)
    log.info("Sodiqlik/toifa qayta hisoblandi: %s ta vrach", updated)


async def run_monthly_close(day: date | None = None) -> None:
    """Har oy 1-sanada o'tgan oy yakuni."""
    day = day or today_local()
    year, month = plans_service.previous_month(day.year, day.month)
    start, end = plans_service.month_bounds(year, month)

    async with session_scope() as session:
        summary = await rp.sales_summary(session, start, end)
        board = await plans_service.leaderboard(session, year, month)
        aging = await rp.debt_aging(session, day)

        rows = [
            f"{index}. {row.full_name} — {plan_emoji(row.overall_pct)} {row.overall_pct:g}% "
            f"({money_usd(row.amount.fact)})"
            for index, row in enumerate(board, start=1)
        ]

        text = "\n".join(
            [
                f"📈 <b>{month}/{year} oyi yakuni</b>",
                "",
                f"  Sotuv: {money_usd(summary['amount_usd'])}",
                f"  Dona: {summary['units']}",
                f"  Buyurtmalar: {summary['orders']}",
                f"  Yig'ilgan pul: {money_usd(summary['collected_usd'])}",
                f"  Xarid qilgan vrachlar: {summary['doctors']}",
                "",
                "<b>👥 Agentlar reytingi</b>",
                "\n".join(rows) if rows else "— ma'lumot yo'q",
                "",
                "<b>💳 Qarz yoshi (oy oxiriga)</b>",
                *[f"  {name}: {money_usd(value)}" for name, value in aging.items()],
            ]
        )

        await notify.send_to_roles(
            session,
            [Role.DIRECTOR, Role.FOUNDER, Role.SUPERADMIN, Role.ACCOUNTANT],
            text,
            kind="monthly_close",
            dedup_key=f"monthly:{year}-{month:02d}",
            button=("Hisobotlarni ochish", "/reports"),
        )

        # Agentlarga shaxsiy yakun
        agents = (
            await session.execute(
                select(User).where(User.role == Role.AGENT, User.is_active.is_(True))
            )
        ).scalars().all()
        for agent in agents:
            progress = await plans_service.progress(session, agent, year, month)
            place = next(
                (i + 1 for i, row in enumerate(board) if row.user_id == agent.id), None
            )
            await notify.send_to_user(
                session,
                agent,
                "\n".join(
                    [
                        f"📈 <b>{month}/{year} oyi yakuni</b>",
                        "",
                        f"  Sotuv: {money_usd(progress.amount.fact)} "
                        f"({progress.amount.pct:g}%)",
                        f"  Dona: {progress.units.fact:g} ({progress.units.pct:g}%)",
                        f"  Yig'ilgan: {money_usd(progress.collection.fact)} "
                        f"({progress.collection.pct:g}%)",
                        "",
                        f"  {plan_emoji(progress.overall_pct)} Umumiy: "
                        f"<b>{progress.overall_pct:g}%</b>"
                        + (f" | Reytingda {place}-o'rin" if place else ""),
                    ]
                ),
                kind="monthly_close_agent",
                dedup_key=f"monthly_agent:{agent.id}:{year}-{month:02d}",
                button=("Rejani ko'rish", "/plan"),
            )

    log.info("Oylik yakun yuborildi: %s/%s", month, year)


async def run_daily_fx_check(day: date | None = None) -> None:
    """Kurs bugunga kiritilmagan bo'lsa — buxgalter va direktorga eslatma."""
    from app.models import FxRate

    day = day or today_local()
    async with session_scope() as session:
        row = await session.get(FxRate, day)
        if row is not None:
            return
        await notify.send_to_roles(
            session,
            [Role.ACCOUNTANT, Role.DIRECTOR],
            f"💱 <b>Bugungi kurs kiritilmagan</b> ({fmt_date(day)})\n"
            "Hujjatlar oxirgi mavjud kurs bo'yicha rasmiylashtirilmoqda.",
            kind="fx_missing",
            dedup_key=f"fx_missing:{day.isoformat()}",
            button=("Kursni kiritish", "/settings"),
        )
