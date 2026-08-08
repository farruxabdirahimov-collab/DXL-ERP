"""USD/UZS kursi bilan ishlash.

Narx va qarz USD'da, to'lov so'mda. Har hujjat o'zi yaratilgan kundagi kursni
saqlaydi va keyin kurs o'zgarsa ham o'sha hujjatga ta'sir qilmaydi.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import FxRate, User, utcnow

CENT = Decimal("0.01")


def today_local() -> date:
    return utcnow().astimezone(settings.timezone).date()


def round_money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


async def get_rate(session: AsyncSession, on_date: date | None = None) -> Decimal:
    """Berilgan sanadagi (yoki undan oldingi eng yaqin) kurs."""
    on_date = on_date or today_local()
    row = (
        await session.execute(
            select(FxRate)
            .where(FxRate.rate_date <= on_date)
            .order_by(FxRate.rate_date.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if row is not None:
        return Decimal(row.usd_uzs)
    return Decimal(str(settings.default_usd_uzs))


async def set_rate(
    session: AsyncSession, value: Decimal, on_date: date | None = None, user: User | None = None
) -> FxRate:
    on_date = on_date or today_local()
    row = await session.get(FxRate, on_date)
    if row is None:
        row = FxRate(rate_date=on_date, usd_uzs=value, created_at=utcnow())
        session.add(row)
    else:
        row.usd_uzs = value
    if user is not None:
        row.set_by_id = user.id
    await session.flush()
    return row


def usd_to_uzs(amount_usd: Decimal, rate: Decimal) -> Decimal:
    return round_money(Decimal(amount_usd) * Decimal(rate))


def uzs_to_usd(amount_uzs: Decimal, rate: Decimal) -> Decimal:
    if not rate:
        raise ValueError("Kurs nolga teng bo'lishi mumkin emas")
    return round_money(Decimal(amount_uzs) / Decimal(rate))
