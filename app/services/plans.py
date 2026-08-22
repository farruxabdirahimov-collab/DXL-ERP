"""Agentning oylik rejasi va bajarilishi.

Uchta ko'rsatkich: sotuv summasi (USD), sotilgan dona, yig'ilgan pul (USD).
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass, asdict
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import (
    Order,
    OrderItem,
    OrderStatus,
    Payment,
    Return,
    ReturnItem,
    Role,
    SalesPlan,
    User,
)
from app.services.fx import round_money, today_local

ZERO = Decimal("0.00")


def month_bounds(year: int, month: int) -> tuple[datetime, datetime]:
    """Oyning boshi va oxiri (mahalliy vaqt zonasida, aware datetime)."""
    tz = settings.timezone
    last_day = calendar.monthrange(year, month)[1]
    start = datetime.combine(date(year, month, 1), time.min, tzinfo=tz)
    end = datetime.combine(date(year, month, last_day), time.max, tzinfo=tz)
    return start, end


@dataclass
class Metric:
    fact: float
    target: float
    pct: float

    @staticmethod
    def build(fact: Decimal | int | float, target: Decimal | int | float) -> "Metric":
        fact_f = float(fact or 0)
        target_f = float(target or 0)
        pct = round(fact_f / target_f * 100, 1) if target_f > 0 else 0.0
        return Metric(fact=round(fact_f, 2), target=round(target_f, 2), pct=pct)


@dataclass
class PlanProgress:
    user_id: int
    full_name: str
    year: int
    month: int
    amount: Metric
    units: Metric
    collection: Metric
    #: Ixtiyoriy maqsadlar — target 0 bo'lsa umumiy foizga qo'shilmaydi
    new_doctors: Metric
    active_doctors: Metric
    visits: Metric
    overall_pct: float
    days_passed: int
    days_in_month: int
    has_plan: bool

    def to_dict(self) -> dict:
        data = asdict(self)
        return data


async def get_plan(
    session: AsyncSession, user_id: int, year: int, month: int
) -> SalesPlan | None:
    return (
        await session.execute(
            select(SalesPlan).where(
                SalesPlan.user_id == user_id,
                SalesPlan.year == year,
                SalesPlan.month == month,
            )
        )
    ).scalar_one_or_none()


async def upsert_plan(
    session: AsyncSession,
    *,
    user_id: int,
    year: int,
    month: int,
    target_amount_usd: Decimal,
    target_units: int,
    target_collection_usd: Decimal,
    target_new_doctors: int = 0,
    target_active_doctors: int = 0,
    target_visits: int = 0,
    actor: User | None = None,
) -> SalesPlan:
    plan = await get_plan(session, user_id, year, month)
    if plan is None:
        plan = SalesPlan(user_id=user_id, year=year, month=month)
        session.add(plan)
    plan.target_amount_usd = Decimal(target_amount_usd)
    plan.target_units = int(target_units)
    plan.target_collection_usd = Decimal(target_collection_usd)
    plan.target_new_doctors = int(target_new_doctors)
    plan.target_active_doctors = int(target_active_doctors)
    plan.target_visits = int(target_visits)
    if actor is not None:
        plan.created_by_id = actor.id
    await session.flush()
    return plan


async def agent_facts(
    session: AsyncSession, user_id: int, start: datetime, end: datetime
) -> tuple[Decimal, int, Decimal]:
    """(sotuv summasi USD, dona, yig'ilgan pul USD)."""
    amount = (
        await session.execute(
            select(func.coalesce(func.sum(Order.total_usd), 0)).where(
                Order.agent_id == user_id,
                Order.status == OrderStatus.DELIVERED,
                Order.delivered_at >= start,
                Order.delivered_at <= end,
            )
        )
    ).scalar_one()

    units = (
        await session.execute(
            select(func.coalesce(func.sum(OrderItem.qty), 0))
            .join(Order, Order.id == OrderItem.order_id)
            .where(
                Order.agent_id == user_id,
                Order.status == OrderStatus.DELIVERED,
                Order.delivered_at >= start,
                Order.delivered_at <= end,
            )
        )
    ).scalar_one()

    collection = (
        await session.execute(
            select(func.coalesce(func.sum(Payment.amount_usd), 0)).where(
                Payment.agent_id == user_id,
                Payment.paid_at >= start,
                Payment.paid_at <= end,
            )
        )
    ).scalar_one()

    # Qaytarilgan tovar reja bajarilishidan ayiriladi
    returned_amount = (
        await session.execute(
            select(func.coalesce(func.sum(Return.total_usd), 0)).where(
                Return.agent_id == user_id,
                Return.created_at >= start,
                Return.created_at <= end,
            )
        )
    ).scalar_one()
    returned_units = (
        await session.execute(
            select(func.coalesce(func.sum(ReturnItem.qty), 0))
            .join(Return, Return.id == ReturnItem.return_id)
            .where(
                Return.agent_id == user_id,
                Return.created_at >= start,
                Return.created_at <= end,
            )
        )
    ).scalar_one()

    return (
        round_money(Decimal(amount or 0) - Decimal(returned_amount or 0)),
        int(units or 0) - int(returned_units or 0),
        round_money(Decimal(collection or 0)),
    )


async def progress(
    session: AsyncSession,
    agent: User,
    year: int | None = None,
    month: int | None = None,
) -> PlanProgress:
    today = today_local()
    year = year or today.year
    month = month or today.month
    start, end = month_bounds(year, month)

    amount, units, collection = await agent_facts(session, agent.id, start, end)
    plan = await get_plan(session, agent.id, year, month)

    amount_metric = Metric.build(amount, plan.target_amount_usd if plan else 0)
    units_metric = Metric.build(units, plan.target_units if plan else 0)
    collection_metric = Metric.build(
        collection, plan.target_collection_usd if plan else 0
    )

    yangi, faol, tashrif = await agent_extra_facts(session, agent.id, start, end)
    new_doctors_metric = Metric.build(yangi, plan.target_new_doctors if plan else 0)
    active_doctors_metric = Metric.build(faol, plan.target_active_doctors if plan else 0)
    visits_metric = Metric.build(tashrif, plan.target_visits if plan else 0)

    # Faqat qo'yilgan maqsadlar umumiy foizga kiradi
    active = [
        m.pct
        for m in (
            amount_metric, units_metric, collection_metric,
            new_doctors_metric, active_doctors_metric, visits_metric,
        )
        if m.target > 0
    ]
    overall = round(sum(active) / len(active), 1) if active else 0.0

    days_in_month = calendar.monthrange(year, month)[1]
    if (today.year, today.month) == (year, month):
        days_passed = today.day
    elif date(year, month, 1) < today.replace(day=1):
        days_passed = days_in_month
    else:
        days_passed = 0

    return PlanProgress(
        user_id=agent.id,
        full_name=agent.full_name,
        year=year,
        month=month,
        amount=amount_metric,
        units=units_metric,
        collection=collection_metric,
        new_doctors=new_doctors_metric,
        active_doctors=active_doctors_metric,
        visits=visits_metric,
        overall_pct=overall,
        days_passed=days_passed,
        days_in_month=days_in_month,
        has_plan=plan is not None,
    )


async def leaderboard(
    session: AsyncSession, year: int | None = None, month: int | None = None
) -> list[PlanProgress]:
    """Barcha agentlar reytingi (bajarilish foizi bo'yicha)."""
    today = today_local()
    year = year or today.year
    month = month or today.month
    agents = (
        await session.execute(
            select(User).where(User.role == Role.AGENT, User.is_active.is_(True))
        )
    ).scalars().all()

    rows = [await progress(session, agent, year, month) for agent in agents]
    rows.sort(key=lambda p: (p.overall_pct, p.amount.fact), reverse=True)
    return rows


def expected_pace_pct(days_passed: int, days_in_month: int) -> float:
    """Oy davomida kutilayotgan tempda necha foiz bo'lishi kerak edi."""
    if days_in_month <= 0:
        return 0.0
    return round(days_passed / days_in_month * 100, 1)


def previous_month(year: int, month: int) -> tuple[int, int]:
    first = date(year, month, 1) - timedelta(days=1)
    return first.year, first.month


# ==========================================================================
# Modul 2 — kengaytirilgan reja: qo'shimcha ko'rsatkichlar, prognoz, tarix
# ==========================================================================


async def agent_extra_facts(
    session: AsyncSession, user_id: int, start: datetime, end: datetime
) -> tuple[int, int, int]:
    """(yangi vrachlar, faol vrachlar, tashriflar) — davr ichida."""
    from app.models import Doctor, Visit

    yangi = (
        await session.execute(
            select(func.count(Doctor.id)).where(
                Doctor.agent_id == user_id,
                Doctor.created_at >= start,
                Doctor.created_at <= end,
            )
        )
    ).scalar_one()

    # Faol = davr ichida kamida bitta yetkazilgan buyurtmasi bo'lgan vrach
    faol = (
        await session.execute(
            select(func.count(func.distinct(Order.doctor_id))).where(
                Order.agent_id == user_id,
                Order.status == OrderStatus.DELIVERED,
                Order.delivered_at >= start,
                Order.delivered_at <= end,
            )
        )
    ).scalar_one()

    tashrif = (
        await session.execute(
            select(func.count(Visit.id)).where(
                Visit.agent_id == user_id,
                Visit.created_at >= start,
                Visit.created_at <= end,
            )
        )
    ).scalar_one()

    return int(yangi or 0), int(faol or 0), int(tashrif or 0)


@dataclass
class Forecast:
    """Shu sur'atda oy oxirida qancha bo'ladi va rejaga yetish uchun nima kerak."""

    projected_usd: float      # shu sur'atda oy oxirida
    projected_pct: float      # rejaning necha foizi
    daily_so_far_usd: float   # hozirgi o'rtacha kunlik
    daily_needed_usd: float   # rejani bajarish uchun kerakli kunlik
    on_track: bool            # sur'at yetarlimi


def forecast(
    fact_usd: float, target_usd: float, days_passed: int, days_in_month: int
) -> Forecast:
    """Chiziqli prognoz — vrachga emas, agentga ko'rsatiladi."""
    days_passed = max(0, min(days_passed, days_in_month))
    qolgan = days_in_month - days_passed

    daily = fact_usd / days_passed if days_passed > 0 else 0.0
    projected = daily * days_in_month if days_passed > 0 else 0.0
    kerak = max(0.0, target_usd - fact_usd)
    daily_needed = kerak / qolgan if qolgan > 0 else 0.0

    return Forecast(
        projected_usd=round(projected, 2),
        projected_pct=round(projected / target_usd * 100, 1) if target_usd > 0 else 0.0,
        daily_so_far_usd=round(daily, 2),
        daily_needed_usd=round(daily_needed, 2),
        # Sur'at yetarli: hozirgi kunlik hech bo'lmaganda kerakli kunlikcha
        on_track=target_usd <= 0 or daily >= daily_needed,
    )


async def history(
    session: AsyncSession, agent: User, months: int = 6
) -> list[dict]:
    """Oxirgi N oy bajarilishi — grafik uchun, eskisidan yangisiga."""
    today = today_local()
    year, month = today.year, today.month
    natija: list[dict] = []

    for _ in range(months):
        p = await progress(session, agent, year, month)
        natija.append(
            {
                "year": year,
                "month": month,
                "label": f"{month:02d}.{year % 100:02d}",
                "overall_pct": p.overall_pct,
                "amount_fact": p.amount.fact,
                "amount_target": p.amount.target,
                "has_plan": p.has_plan,
            }
        )
        year, month = previous_month(year, month)

    return list(reversed(natija))


# ------------------------------------------------------- kompaniya rejasi
async def get_company_plan(session: AsyncSession, year: int, month: int):
    from app.models import CompanyPlan

    return (
        await session.execute(
            select(CompanyPlan).where(
                CompanyPlan.year == year, CompanyPlan.month == month
            )
        )
    ).scalar_one_or_none()


async def upsert_company_plan(
    session: AsyncSession, *, year: int, month: int, actor: User, **targets
):
    from app.models import CompanyPlan

    plan = await get_company_plan(session, year, month)
    if plan is None:
        plan = CompanyPlan(year=year, month=month, created_by_id=actor.id)
        session.add(plan)
    for key, value in targets.items():
        if value is not None:
            setattr(plan, key, value)
    await session.flush()
    return plan


async def company_progress(
    session: AsyncSession, year: int | None = None, month: int | None = None
) -> dict:
    """Kompaniya rejasi vs haqiqat, va agentlar rejasi bilan solishtirish.

    Agentlarga bo'lingan reja kompaniya rejasidan kam bo'lsa — farq
    «egasiz reja»: kimdir bajarishi kerak, lekin hech kimga biriktirilmagan.
    """
    from app.models import Doctor

    today = today_local()
    year = year or today.year
    month = month or today.month
    start, end = month_bounds(year, month)

    plan = await get_company_plan(session, year, month)
    board = await leaderboard(session, year, month)

    fact_amount = sum(p.amount.fact for p in board)
    fact_units = sum(p.units.fact for p in board)
    fact_collection = sum(p.collection.fact for p in board)

    # Agentlarga taqsimlangan reja
    taqsimlangan = sum(p.amount.target for p in board)

    yangi_vrach = (
        await session.execute(
            select(func.count(Doctor.id)).where(
                Doctor.created_at >= start, Doctor.created_at <= end
            )
        )
    ).scalar_one()

    days_in_month = calendar.monthrange(year, month)[1]
    if (today.year, today.month) == (year, month):
        days_passed = today.day
    elif date(year, month, 1) < today.replace(day=1):
        days_passed = days_in_month
    else:
        days_passed = 0

    target_amount = float(plan.target_amount_usd) if plan else 0.0
    fc = forecast(fact_amount, target_amount, days_passed, days_in_month)

    return {
        "year": year,
        "month": month,
        "has_plan": plan is not None,
        "days_passed": days_passed,
        "days_in_month": days_in_month,
        "amount": asdict(Metric.build(fact_amount, target_amount)),
        "units": asdict(
            Metric.build(fact_units, plan.target_units if plan else 0)
        ),
        "collection": asdict(
            Metric.build(
                fact_collection, plan.target_collection_usd if plan else 0
            )
        ),
        "new_doctors": asdict(
            Metric.build(yangi_vrach, plan.target_new_doctors if plan else 0)
        ),
        "forecast": asdict(fc),
        # Taqsimot nazorati
        "assigned_usd": round(taqsimlangan, 2),
        "unassigned_usd": round(max(0.0, target_amount - taqsimlangan), 2),
        "agents_with_plan": sum(1 for p in board if p.has_plan),
        "agents_total": len(board),
    }


async def copy_from_previous(
    session: AsyncSession, *, year: int, month: int, actor: User
) -> int:
    """O'tgan oy rejalarini shu oyga nusxalaydi.

    Reja qo'yishni bir bosishga tushiradi — eng ko'p vaqt oladigan ish shu.
    Rejasi allaqachon qo'yilgan agent o'tkazib yuboriladi.
    """
    o_yil, o_oy = previous_month(year, month)
    eskilar = (
        await session.execute(
            select(SalesPlan).where(SalesPlan.year == o_yil, SalesPlan.month == o_oy)
        )
    ).scalars().all()

    nusxalandi = 0
    for eski in eskilar:
        if await get_plan(session, eski.user_id, year, month) is not None:
            continue
        await upsert_plan(
            session,
            user_id=eski.user_id,
            year=year,
            month=month,
            target_amount_usd=eski.target_amount_usd,
            target_units=eski.target_units,
            target_collection_usd=eski.target_collection_usd,
            target_new_doctors=eski.target_new_doctors,
            target_active_doctors=eski.target_active_doctors,
            target_visits=eski.target_visits,
            actor=actor,
        )
        nusxalandi += 1

    return nusxalandi


async def apply_to_all_agents(
    session: AsyncSession, *, year: int, month: int, actor: User, **targets
) -> int:
    """Barcha faol agentlarga bir xil reja qo'yadi."""
    from app.models import Role

    agentlar = (
        await session.execute(
            select(User).where(User.role == Role.AGENT, User.is_active.is_(True))
        )
    ).scalars().all()

    for agent in agentlar:
        await upsert_plan(
            session, user_id=agent.id, year=year, month=month, actor=actor, **targets
        )
    return len(agentlar)
