"""To'lovlar: so'mda qabul qilinadi, USD qarzni yopadi."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Doctor, Payment, PaymentMethod, Role, User, utcnow
from app.services.debt import allocate_payment
from app.services.fx import get_rate, round_money, today_local, uzs_to_usd


class PaymentError(Exception):
    pass


async def create_payment(
    session: AsyncSession,
    *,
    doctor: Doctor,
    amount_uzs: Decimal,
    method: PaymentMethod,
    actor: User,
    order_id: int | None = None,
    paid_at: datetime | None = None,
    fx_rate: Decimal | None = None,
    note: str | None = None,
) -> tuple[Payment, Decimal]:
    """To'lovni yozadi va qarzlarga taqsimlaydi.

    Qaytaradi: (to'lov, taqsimlanmagan avans USD)
    """
    if Decimal(amount_uzs) <= 0:
        raise PaymentError("To'lov summasi 0 dan katta bo'lishi kerak")

    rate = Decimal(fx_rate) if fx_rate else await get_rate(session, today_local())
    if rate <= 0:
        raise PaymentError("Valyuta kursi noto'g'ri")

    amount_usd = uzs_to_usd(Decimal(amount_uzs), rate)

    # Reja "yig'ilgan pul" ko'rsatkichi vrachning agentiga yoziladi
    agent_id = doctor.agent_id
    if agent_id is None and actor.role is Role.AGENT:
        agent_id = actor.id

    payment = Payment(
        doctor_id=doctor.id,
        order_id=order_id,
        amount_uzs=round_money(Decimal(amount_uzs)),
        fx_rate=rate,
        amount_usd=amount_usd,
        method=method,
        paid_at=paid_at or utcnow(),
        received_by_id=actor.id,
        agent_id=agent_id,
        note=note,
    )
    session.add(payment)
    await session.flush()

    advance = await allocate_payment(session, payment)
    return payment, advance
