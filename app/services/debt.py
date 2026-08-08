"""Qarz hisobi, muddat nazorati va to'lovni taqsimlash.

Qarz USD'da yuritiladi. Har buyurtmaning `due_date` = yetkazilgan sana +
vrachning `payment_term_days` kuni.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Doctor,
    Order,
    OrderStatus,
    Payment,
    PaymentAllocation,
    utcnow,
)
from app.services.fx import round_money, today_local
from app.services.settings_service import get_setting

ZERO = Decimal("0.00")

#: Qarz yoshlanishi (aging) oynalari — kunlarda
AGING_BUCKETS: tuple[tuple[str, int, int | None], ...] = (
    ("muddati kelmagan", -10_000, 0),
    ("0-30 kun", 0, 30),
    ("31-60 kun", 31, 60),
    ("61-90 kun", 61, 90),
    ("90+ kun", 91, None),
)


@dataclass
class DebtSummary:
    total_usd: Decimal = ZERO
    overdue_usd: Decimal = ZERO
    not_due_usd: Decimal = ZERO
    oldest_due_date: date | None = None
    max_overdue_days: int = 0
    open_orders: int = 0
    buckets: dict[str, Decimal] = field(default_factory=dict)


def _debt_expr():
    return Order.total_usd - Order.paid_usd - Order.returned_usd


def unpaid_orders_stmt(doctor_id: int | None = None):
    """Yopilmagan (qarzi qolgan) yetkazilgan buyurtmalar."""
    stmt = select(Order).where(
        Order.status == OrderStatus.DELIVERED,
        _debt_expr() > Decimal("0.005"),
    )
    if doctor_id is not None:
        stmt = stmt.where(Order.doctor_id == doctor_id)
    return stmt.order_by(Order.due_date.asc().nullsfirst(), Order.id.asc())


async def doctor_debt(
    session: AsyncSession, doctor_id: int, on_date: date | None = None
) -> DebtSummary:
    """Bitta vrachning qarzi: umumiy, muddati o'tgan, yoshlanish bo'yicha."""
    on_date = on_date or today_local()
    orders = (await session.execute(unpaid_orders_stmt(doctor_id))).scalars().all()

    summary = DebtSummary(buckets={name: ZERO for name, _, _ in AGING_BUCKETS})
    for order in orders:
        debt = round_money(order.total_usd - order.paid_usd - order.returned_usd)
        if debt <= 0:
            continue
        summary.total_usd += debt
        summary.open_orders += 1

        due = order.due_date
        if due is None:
            summary.buckets["0-30 kun"] += debt
            continue

        overdue_days = (on_date - due).days
        if overdue_days > 0:
            summary.overdue_usd += debt
            summary.max_overdue_days = max(summary.max_overdue_days, overdue_days)
            if summary.oldest_due_date is None or due < summary.oldest_due_date:
                summary.oldest_due_date = due
        else:
            summary.not_due_usd += debt

        for name, lo, hi in AGING_BUCKETS:
            if overdue_days >= lo and (hi is None or overdue_days <= hi):
                summary.buckets[name] += debt
                break

    summary.total_usd = round_money(summary.total_usd)
    summary.overdue_usd = round_money(summary.overdue_usd)
    summary.not_due_usd = round_money(summary.not_due_usd)
    return summary


async def total_debt(session: AsyncSession, on_date: date | None = None) -> dict:
    """Butun tashkilot bo'yicha qarz va muddati o'tgan qarz."""
    on_date = on_date or today_local()
    total = (
        await session.execute(
            select(func.coalesce(func.sum(_debt_expr()), 0)).where(
                Order.status == OrderStatus.DELIVERED, _debt_expr() > Decimal("0.005")
            )
        )
    ).scalar_one()
    overdue = (
        await session.execute(
            select(func.coalesce(func.sum(_debt_expr()), 0)).where(
                Order.status == OrderStatus.DELIVERED,
                _debt_expr() > Decimal("0.005"),
                Order.due_date.is_not(None),
                Order.due_date < on_date,
            )
        )
    ).scalar_one()
    doctors_in_debt = (
        await session.execute(
            select(func.count(func.distinct(Order.doctor_id))).where(
                Order.status == OrderStatus.DELIVERED, _debt_expr() > Decimal("0.005")
            )
        )
    ).scalar_one()
    return {
        "total_usd": round_money(Decimal(total or 0)),
        "overdue_usd": round_money(Decimal(overdue or 0)),
        "doctors_in_debt": int(doctors_in_debt or 0),
    }


async def allocate_payment(session: AsyncSession, payment: Payment) -> Decimal:
    """To'lovni buyurtmalarga taqsimlaydi (eng eski muddatdan boshlab).

    Qaytaradi: taqsimlanmagan qoldiq (avans).
    """
    remaining = round_money(payment.amount_usd)

    if payment.order_id:
        orders = [await session.get(Order, payment.order_id)]
        orders = [o for o in orders if o is not None]
    else:
        orders = list(
            (await session.execute(unpaid_orders_stmt(payment.doctor_id))).scalars().all()
        )

    for order in orders:
        if remaining <= 0:
            break
        debt = round_money(order.total_usd - order.paid_usd - order.returned_usd)
        if debt <= 0:
            continue
        applied = min(debt, remaining)
        order.paid_usd = round_money(order.paid_usd + applied)
        if order.paid_usd + order.returned_usd >= order.total_usd:
            order.closed_at = utcnow()
        session.add(
            PaymentAllocation(
                payment_id=payment.id, order_id=order.id, amount_usd=applied
            )
        )
        remaining = round_money(remaining - applied)

    await session.flush()
    return remaining


async def credit_check(
    session: AsyncSession, doctor: Doctor, new_order_usd: Decimal
) -> str | None:
    """Yangi buyurtma direktor tasdig'ini talab qiladimi? Sabab yoki None."""
    if doctor.credit_block_override:
        return None

    block_on_limit = bool(await get_setting(session, "block_on_debt_limit"))
    block_on_overdue = bool(await get_setting(session, "block_on_overdue"))

    summary = await doctor_debt(session, doctor.id)

    if block_on_overdue and summary.overdue_usd > 0:
        return (
            f"Muddati o'tgan qarz: ${summary.overdue_usd} "
            f"({summary.max_overdue_days} kun kechikkan)"
        )

    if block_on_limit:
        limit = Decimal(doctor.debt_limit_usd or 0)
        after = summary.total_usd + round_money(new_order_usd)
        if after > limit:
            return (
                f"Qarz limitidan oshadi: limit ${limit}, "
                f"buyurtmadan keyin ${after}"
            )
    return None


def compute_due_date(delivered_on: date, doctor: Doctor) -> date:
    return delivered_on + timedelta(days=int(doctor.payment_term_days or 0))


async def overdue_orders(
    session: AsyncSession, on_date: date | None = None, agent_id: int | None = None
) -> list[Order]:
    """Muddati o'tgan qarzli buyurtmalar."""
    on_date = on_date or today_local()
    stmt = select(Order).where(
        Order.status == OrderStatus.DELIVERED,
        _debt_expr() > Decimal("0.005"),
        Order.due_date.is_not(None),
        Order.due_date < on_date,
    )
    if agent_id is not None:
        stmt = stmt.where(Order.agent_id == agent_id)
    return list((await session.execute(stmt.order_by(Order.due_date))).scalars().all())


async def due_soon_orders(
    session: AsyncSession, days: int = 3, on_date: date | None = None
) -> list[Order]:
    """Yaqin kunlarda muddati tugaydigan qarzlar."""
    on_date = on_date or today_local()
    stmt = select(Order).where(
        Order.status == OrderStatus.DELIVERED,
        _debt_expr() > Decimal("0.005"),
        and_(
            Order.due_date >= on_date,
            Order.due_date <= on_date + timedelta(days=days),
        ),
    )
    return list((await session.execute(stmt.order_by(Order.due_date))).scalars().all())
