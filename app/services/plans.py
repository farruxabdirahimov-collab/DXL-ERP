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
from app.models import Order, OrderItem, OrderStatus, Payment, Role, SalesPlan, User
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
    actor: User | None = None,
) -> SalesPlan:
    plan = await get_plan(session, user_id, year, month)
    if plan is None:
        plan = SalesPlan(user_id=user_id, year=year, month=month)
        session.add(plan)
    plan.target_amount_usd = Decimal(target_amount_usd)
    plan.target_units = int(target_units)
    plan.target_collection_usd = Decimal(target_collection_usd)
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

    return (
        round_money(Decimal(amount or 0)),
        int(units or 0),
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

    active = [m.pct for m in (amount_metric, units_metric, collection_metric) if m.target > 0]
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
