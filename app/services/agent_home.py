"""Agent bosh ekrani — bitta so'rovda hamma narsa.

Agent kuniga 10-12 marta ochadi, ko'pincha sekin internetda. Shuning
uchun bosh ekran uchta alohida so'rov emas, bitta javob oladi.

Mazmuni «statistika» emas, «bugun nima qilaman»:
    1. Bu oy topgan puli va bugun qancha qo'shildi
    2. Bugungi tashrif maqsadi (qolganini qolgan kunlarga bo'lib)
    3. Shoshilinch ro'yxat — bugun kimga qo'ng'iroq qilish kerak
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    ContentSubmission,
    Contract,
    ContractStatus,
    Doctor,
    Payment,
    SubmissionStatus,
    User,
    Visit,
)
from app.services import contracts as contracts_service
from app.services import kpi
from app.services.fx import round_money, today_local
from app.services.plans import month_bounds
from app.services.reports import day_bounds

ZERO = Decimal("0")

#: «Oz qoldi» deb hisoblanadigan chegara — bir qo'ng'iroq bilan yopiladi
DEYARLI_TOLANGAN_PCT = 85


async def _today_earned(session: AsyncSession, agent: User, day: date) -> Decimal:
    """Bugungi harakatlardan qancha qo'shildi.

    Tashrif va post — dona bo'yicha aniq narx. Yig'ilgan pul — joriy
    foizda (oy oxirida foiz o'zgarishi mumkin, shuning uchun taxminiy).
    """
    start, end = day_bounds(day)

    tashrif = int(
        (
            await session.execute(
                select(func.count(Visit.id)).where(
                    Visit.agent_id == agent.id,
                    Visit.created_at >= start,
                    Visit.created_at <= end,
                )
            )
        ).scalar_one()
        or 0
    )

    yigim = Decimal(
        (
            await session.execute(
                select(func.coalesce(func.sum(Payment.amount_usd), 0)).where(
                    Payment.agent_id == agent.id,
                    Payment.paid_at >= start,
                    Payment.paid_at <= end,
                )
            )
        ).scalar_one()
        or 0
    )

    postlar = int(
        (
            await session.execute(
                select(func.count(ContentSubmission.id)).where(
                    ContentSubmission.agent_id == agent.id,
                    ContentSubmission.status == SubmissionStatus.APPROVED,
                    ContentSubmission.reviewed_at >= start,
                    ContentSubmission.reviewed_at <= end,
                )
            )
        ).scalar_one()
        or 0
    )

    # Oylik yig'imga qaysi foiz tushayotganini olamiz — bugungi ulushi shunda
    m_start, m_end = month_bounds(day.year, day.month)
    oylik_yigim = Decimal(
        (
            await session.execute(
                select(func.coalesce(func.sum(Payment.amount_usd), 0)).where(
                    Payment.agent_id == agent.id,
                    Payment.paid_at >= m_start,
                    Payment.paid_at <= m_end,
                )
            )
        ).scalar_one()
        or 0
    )
    _, foiz = kpi.collection_pay(oylik_yigim)

    return round_money(
        kpi.visit_pay(tashrif)
        + yigim * foiz / Decimal("100")
        + kpi.POST_NARX_USD * postlar
    )


def _daily_target(done: int, day: date) -> int:
    """Bugun nechta tashrif kerak — qolganini qolgan kunlarga bo'lib.

    Qat'iy raqam emas: agent ortda qolsa ertangi maqsad ko'tariladi,
    oldinda bo'lsa tushadi. O'z-o'zini to'g'rilaydi.
    """
    import calendar

    kunlar = calendar.monthrange(day.year, day.month)[1]
    qolgan_kun = max(1, kunlar - day.day + 1)
    qolgan_tashrif = max(0, kpi.TASHRIF_MAQSAD - done)
    return -(-qolgan_tashrif // qolgan_kun)  # yuqoriga yaxlitlash


async def _urgent(session: AsyncSession, agent: User, day: date) -> list[dict]:
    """Bugun e'tibor talab qiladigan shartnomalar — shoshilinchi birinchi."""
    rows = (
        await session.execute(
            select(Contract, Doctor.full_name, Doctor.phone)
            .join(Doctor, Doctor.id == Contract.doctor_id)
            .where(
                Contract.status == ContractStatus.ACTIVE,
                Contract.agent_id == agent.id,
            )
            .order_by(Contract.deadline_at)
        )
    ).all()

    natija = []
    for contract, ism, telefon in rows:
        qoldi = contract.remaining_usd
        if qoldi <= 0:
            continue
        cd = contracts_service.countdown(contract)
        if cd.expired:
            continue

        kun = cd.total_seconds / 86400
        deyarli = contract.paid_pct >= DEYARLI_TOLANGAN_PCT

        # Uchta holatdan biri bo'lsa ro'yxatga tushadi
        if not (kun <= 3 or deyarli):
            continue

        natija.append(
            {
                "contract_id": contract.id,
                "doctor_id": contract.doctor_id,
                "doctor_name": ism,
                "phone": telefon,
                "remaining_usd": qoldi,
                "paid_pct": round(contract.paid_pct, 1),
                "deadline_at": cd.deadline_at.isoformat(),
                "server_now": cd.server_now.isoformat(),
                "remaining_seconds": cd.total_seconds,
                # Nima uchun ro'yxatda — agent sababini ko'rsin
                "reason": (
                    f"{contract.paid_pct:.0f}% to'lagan — bir qo'ng'iroq yetadi"
                    if deyarli
                    else "Muddat tugayapti"
                ),
                "almost_done": deyarli,
            }
        )

    # Deyarli to'langanlar tepada: eng arzon pul shu yerda
    natija.sort(key=lambda r: (not r["almost_done"], r["remaining_seconds"]))
    return natija


async def build(session: AsyncSession, agent: User) -> dict:
    """Agent bosh ekrani uchun to'liq javob."""
    bugun = today_local()
    m_start, m_end = month_bounds(bugun.year, bugun.month)
    d_start, d_end = day_bounds(bugun)

    oylik = await kpi.salary(session, agent, bugun.year, bugun.month)

    oydagi_tashrif = int(
        (
            await session.execute(
                select(func.count(Visit.id)).where(
                    Visit.agent_id == agent.id,
                    Visit.created_at >= m_start,
                    Visit.created_at <= m_end,
                )
            )
        ).scalar_one()
        or 0
    )
    bugungi_tashrif = int(
        (
            await session.execute(
                select(func.count(Visit.id)).where(
                    Visit.agent_id == agent.id,
                    Visit.created_at >= d_start,
                    Visit.created_at <= d_end,
                )
            )
        ).scalar_one()
        or 0
    )

    maqsad = _daily_target(oydagi_tashrif, bugun)

    return {
        "date": bugun.isoformat(),
        "first_name": agent.full_name.split(" ")[0],
        # 1. Pul
        "month_earned_usd": oylik["total_usd"],
        "today_earned_usd": await _today_earned(session, agent, bugun),
        "month_pending_usd": oylik["potential_usd"],
        # 2. Kunlik halqa
        "visits_today": bugungi_tashrif,
        "visits_target_today": maqsad,
        "visits_month": oydagi_tashrif,
        "visits_target_month": kpi.TASHRIF_MAQSAD,
        # Yana bittasi qancha pul keltiradi — turtki shu
        "per_visit_usd": round_money(
            kpi.TASHRIF_BONUS_USD / kpi.TASHRIF_MAQSAD
        ),
        # 3. Shoshilinch
        "urgent": await _urgent(session, agent, bugun),
    }


async def nearby_doctors(
    session: AsyncSession, agent: User, lat: float, lon: float, limit: int = 5
) -> list[dict]:
    """Eng yaqin vrachlar — tashrif bir bosishda qayd etilishi uchun."""
    from app.permissions import doctor_scope
    from app.utils.geo import haversine_m

    stmt = select(Doctor).where(
        Doctor.is_active.is_(True),
        Doctor.lat.is_not(None),
        Doctor.lon.is_not(None),
    )
    if doctor_scope(agent) is not None:
        stmt = stmt.where(Doctor.agent_id == agent.id)

    rows = (await session.execute(stmt)).scalars().all()

    bilan_masofa = [
        (haversine_m(lat, lon, doctor.lat, doctor.lon), doctor) for doctor in rows
    ]
    bilan_masofa.sort(key=lambda x: x[0])

    return [
        {
            "id": doctor.id,
            "full_name": doctor.full_name,
            "clinic_name": doctor.clinic_name,
            "phone": doctor.phone,
            "distance_m": round(masofa),
        }
        for masofa, doctor in bilan_masofa[:limit]
    ]
