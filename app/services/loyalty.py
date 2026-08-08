"""Vrachlarning xarid darajasi (A/B/C) va sodiqlik ko'rsatkichi.

Har kecha qayta hisoblanadi. Formula `settings` orqali sozlanadi.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Doctor, DoctorCategory, Order, OrderItem, OrderStatus, utcnow
from app.services.fx import round_money, today_local
from app.services.settings_service import get_setting

ZERO = Decimal("0.00")

#: Sodiqlik hisobida ishlatiladigan me'yorlar
RECENCY_HORIZON_DAYS = 180   # shuncha kundan keyin "recency" bali 0 ga tushadi
FREQUENCY_TARGET = 12        # yiliga 12 buyurtma = to'liq ball
DISCIPLINE_HORIZON_DAYS = 30  # o'rtacha 30 kun kechikish = 0 ball


@dataclass
class DoctorMetrics:
    purchased_12m_usd: Decimal = ZERO
    orders_12m: int = 0
    total_purchased_usd: Decimal = ZERO
    units_12m: int = 0
    last_order_at: datetime | None = None
    avg_payment_delay_days: float = 0.0


def loyalty_score(
    metrics: DoctorMetrics,
    *,
    reference_amount_usd: Decimal,
    on_date: date,
    weights: dict[str, float] | None = None,
) -> int:
    """0-100 oralig'idagi sodiqlik bali.

    * Recency  — oxirgi xariddan qancha vaqt o'tgani
    * Frequency — 12 oydagi buyurtmalar soni
    * Monetary — 12 oylik summa (eng yirik mijozga nisbatan)
    * Discipline — to'lov intizomi (o'rtacha kechikish)
    """
    w = {"recency": 25.0, "frequency": 25.0, "monetary": 25.0, "discipline": 25.0}
    if weights:
        w.update({k: float(v) for k, v in weights.items() if k in w})

    if metrics.last_order_at is None:
        recency = 0.0
    else:
        days = (on_date - metrics.last_order_at.date()).days
        recency = max(0.0, 1.0 - days / RECENCY_HORIZON_DAYS)

    frequency = min(1.0, metrics.orders_12m / FREQUENCY_TARGET) if FREQUENCY_TARGET else 0.0

    if reference_amount_usd and reference_amount_usd > 0:
        monetary = min(1.0, float(metrics.purchased_12m_usd) / float(reference_amount_usd))
    else:
        monetary = 0.0

    discipline = max(
        0.0, 1.0 - (metrics.avg_payment_delay_days / DISCIPLINE_HORIZON_DAYS)
    )

    score = (
        recency * w["recency"]
        + frequency * w["frequency"]
        + monetary * w["monetary"]
        + discipline * w["discipline"]
    )
    return int(round(max(0.0, min(100.0, score))))


def assign_categories(
    ranked_doctor_ids: list[int], a_pct: float, b_pct: float
) -> dict[int, DoctorCategory]:
    """Sotuv summasi bo'yicha kamayish tartibida saralangan ro'yxatdan A/B/C."""
    total = len(ranked_doctor_ids)
    if total == 0:
        return {}
    a_cut = max(1, round(total * a_pct / 100)) if a_pct > 0 else 0
    b_cut = max(a_cut, round(total * b_pct / 100)) if b_pct > 0 else a_cut

    result: dict[int, DoctorCategory] = {}
    for index, doctor_id in enumerate(ranked_doctor_ids):
        if index < a_cut:
            result[doctor_id] = DoctorCategory.A
        elif index < b_cut:
            result[doctor_id] = DoctorCategory.B
        else:
            result[doctor_id] = DoctorCategory.C
    return result


async def collect_metrics(session: AsyncSession, on_date: date) -> dict[int, DoctorMetrics]:
    """Barcha vrachlar bo'yicha 12 oylik ko'rsatkichlar."""
    since = datetime.combine(on_date - timedelta(days=365), datetime.min.time())
    metrics: dict[int, DoctorMetrics] = {}

    rows = (
        await session.execute(
            select(
                Order.doctor_id,
                func.count(Order.id),
                func.coalesce(func.sum(Order.total_usd), 0),
                func.max(Order.delivered_at),
            )
            .where(Order.status == OrderStatus.DELIVERED, Order.delivered_at >= since)
            .group_by(Order.doctor_id)
        )
    ).all()
    for doctor_id, count, amount, last_at in rows:
        metrics.setdefault(doctor_id, DoctorMetrics())
        m = metrics[doctor_id]
        m.orders_12m = int(count or 0)
        m.purchased_12m_usd = round_money(Decimal(amount or 0))
        m.last_order_at = last_at

    all_time = (
        await session.execute(
            select(Order.doctor_id, func.coalesce(func.sum(Order.total_usd), 0), func.max(Order.delivered_at))
            .where(Order.status == OrderStatus.DELIVERED)
            .group_by(Order.doctor_id)
        )
    ).all()
    for doctor_id, amount, last_at in all_time:
        m = metrics.setdefault(doctor_id, DoctorMetrics())
        m.total_purchased_usd = round_money(Decimal(amount or 0))
        if m.last_order_at is None:
            m.last_order_at = last_at

    units = (
        await session.execute(
            select(Order.doctor_id, func.coalesce(func.sum(OrderItem.qty), 0))
            .join(OrderItem, OrderItem.order_id == Order.id)
            .where(Order.status == OrderStatus.DELIVERED, Order.delivered_at >= since)
            .group_by(Order.doctor_id)
        )
    ).all()
    for doctor_id, qty in units:
        metrics.setdefault(doctor_id, DoctorMetrics()).units_12m = int(qty or 0)

    # To'lov intizomi: yopilgan buyurtmalar bo'yicha o'rtacha kechikish + hozirgi kechikish
    delay_rows = (
        await session.execute(
            select(Order.doctor_id, Order.due_date, Order.closed_at, Order.total_usd,
                   Order.paid_usd, Order.returned_usd)
            .where(
                Order.status == OrderStatus.DELIVERED,
                Order.delivered_at >= since,
                Order.due_date.is_not(None),
            )
        )
    ).all()
    delays: dict[int, list[float]] = {}
    for doctor_id, due_date, closed_at, total, paid, returned in delay_rows:
        if closed_at is not None:
            days = (closed_at.date() - due_date).days
        elif Decimal(total or 0) - Decimal(paid or 0) - Decimal(returned or 0) > Decimal("0.005"):
            days = (on_date - due_date).days
        else:
            days = 0
        delays.setdefault(doctor_id, []).append(max(0.0, float(days)))
    for doctor_id, values in delays.items():
        metrics.setdefault(doctor_id, DoctorMetrics()).avg_payment_delay_days = round(
            sum(values) / len(values), 1
        )

    return metrics


async def recalculate(session: AsyncSession, on_date: date | None = None) -> int:
    """Barcha vrachlarning toifasi va sodiqlik balini yangilaydi. Nechta yangilangani."""
    on_date = on_date or today_local()
    thresholds = await get_setting(session, "abc_thresholds") or {}
    weights = await get_setting(session, "loyalty_weights") or {}
    a_pct = float(thresholds.get("a_pct", 20))
    b_pct = float(thresholds.get("b_pct", 50))

    metrics = await collect_metrics(session, on_date)
    doctors = (await session.execute(select(Doctor))).scalars().all()

    buyers = [
        (d.id, metrics[d.id].purchased_12m_usd)
        for d in doctors
        if d.id in metrics and metrics[d.id].purchased_12m_usd > 0
    ]
    buyers.sort(key=lambda pair: pair[1], reverse=True)
    categories = assign_categories([doc_id for doc_id, _ in buyers], a_pct, b_pct)

    reference = buyers[0][1] if buyers else ZERO

    updated = 0
    for doctor in doctors:
        m = metrics.get(doctor.id, DoctorMetrics())
        doctor.purchased_12m_usd = m.purchased_12m_usd
        doctor.orders_12m = m.orders_12m
        doctor.total_purchased_usd = m.total_purchased_usd
        doctor.avg_payment_delay_days = m.avg_payment_delay_days
        if m.last_order_at is not None:
            doctor.last_order_at = m.last_order_at
        doctor.category = categories.get(doctor.id, DoctorCategory.NEW)
        doctor.loyalty_score = loyalty_score(
            m, reference_amount_usd=reference, on_date=on_date, weights=weights
        )
        doctor.metrics_updated_at = utcnow()
        updated += 1

    await session.flush()
    return updated


async def sleeping_doctors(
    session: AsyncSession, days: int, agent_id: int | None = None
) -> list[Doctor]:
    """Uzoq vaqt xarid qilmagan ("uxlab qolgan") mijozlar."""
    cutoff = utcnow() - timedelta(days=days)
    stmt = select(Doctor).where(
        Doctor.is_active.is_(True),
        Doctor.last_order_at.is_not(None),
        Doctor.last_order_at < cutoff,
    )
    if agent_id is not None:
        stmt = stmt.where(Doctor.agent_id == agent_id)
    return list(
        (await session.execute(stmt.order_by(Doctor.last_order_at))).scalars().all()
    )


def upcoming_birthdays_filter(doctors: list[Doctor], on_date: date, days: int) -> list[Doctor]:
    """Yaqin `days` kun ichida tug'ilgan kuni bo'lgan vrachlar (yilni hisobga olmay)."""
    result = []
    for doctor in doctors:
        if not doctor.birth_date:
            continue
        for offset in range(days + 1):
            target = on_date + timedelta(days=offset)
            if (doctor.birth_date.month, doctor.birth_date.day) == (target.month, target.day):
                result.append(doctor)
                break
    return result
