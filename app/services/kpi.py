"""Menejer (sotuv agenti) oylik ish haqi — KPI bo'yicha avtomatik hisob.

Barcha pul raqamlari SHU YERDA, bitta joyda. O'zgartirish kerak bo'lsa
faqat quyidagi doimiylar tahrirlanadi — mantiqqa tegilmaydi.

Tarkib:
    1. Fiksa                    — oylik doimiy
    2. Tashrif                  — 250 klinika = $150, nisbatan
    3. Yig'ilgan pul            — 2.5% yoki 3% (chegaradan oshsa butun summaga)
    4. Post / video             — 5 tadan 12 tagacha har biri $5
    5. Shifokor otzivi          — xuddi shunday
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    ContentSubmission,
    Payment,
    Role,
    SubmissionKind,
    SubmissionStatus,
    User,
    Visit,
)
from app.services.fx import round_money, today_local
from app.services.plans import month_bounds

ZERO = Decimal("0")

# --------------------------------------------------------------- qoidalar
#: 1. Oylik doimiy maosh
FIKSA_USD = Decimal("200")

#: 2. Tashrif: shuncha klinikaga borsa — shuncha pul. Kam bo'lsa nisbatan.
TASHRIF_MAQSAD = 250
TASHRIF_BONUS_USD = Decimal("150")

#: 3. Yig'ilgan pul foizi. Chegaradan oshsa butun summaga yuqori foiz.
YIGIM_CHEGARA_USD = Decimal("4000")
YIGIM_PAST_FOIZ = Decimal("2.5")
YIGIM_YUQORI_FOIZ = Decimal("3")

#: 4-5. Post va otziv: shu songacha to'lanmaydi, undan keyin har biriga narx,
#: yuqori chegaradan oshsa ko'paymaydi.
POST_MIN = 5          # shu sondan boshlab to'lanadi (4 tagacha $0)
POST_MAX = 12         # shu sondan keyin ko'paymaydi
POST_NARX_USD = Decimal("5")


@dataclass
class KpiRow:
    """Ish haqining bitta tarkibiy qismi."""

    key: str
    label: str
    fact: float           # haqiqiy natija (dona yoki summa)
    target: float         # maqsad (0 — maqsad yo'q)
    amount_usd: Decimal   # shu qism uchun to'lanadigan pul
    note: str


def visit_pay(count: int) -> Decimal:
    """Tashrif haqi — nisbatan, lekin maqsaddan oshsa ko'paymaydi."""
    if count <= 0 or TASHRIF_MAQSAD <= 0:
        return ZERO
    ulush = min(Decimal(count) / Decimal(TASHRIF_MAQSAD), Decimal("1"))
    return round_money(TASHRIF_BONUS_USD * ulush)


def collection_pay(amount_usd: Decimal) -> tuple[Decimal, Decimal]:
    """Yig'ilgan pul bo'nusi. Qaytaradi: (summa, qo'llanilgan foiz).

    Chegaradan oshsa butun summaga yuqori foiz qo'llanadi — shuning uchun
    chegarani kesib o'tish menejerga sezilarli foyda beradi.
    """
    amount = Decimal(amount_usd or 0)
    if amount <= 0:
        return ZERO, YIGIM_PAST_FOIZ
    foiz = YIGIM_YUQORI_FOIZ if amount >= YIGIM_CHEGARA_USD else YIGIM_PAST_FOIZ
    return round_money(amount * foiz / Decimal("100")), foiz


def content_pay(count: int) -> Decimal:
    """Post/otziv haqi: 4 tagacha $0, 5-12 har biri $5, 13+ ham $60."""
    if count < POST_MIN:
        return ZERO
    return round_money(POST_NARX_USD * min(count, POST_MAX))


# ------------------------------------------------------------- ma'lumot
async def _visit_count(session: AsyncSession, agent_id: int, start, end) -> int:
    return int(
        (
            await session.execute(
                select(func.count(Visit.id)).where(
                    Visit.agent_id == agent_id,
                    Visit.created_at >= start,
                    Visit.created_at <= end,
                )
            )
        ).scalar_one()
        or 0
    )


async def _collected(session: AsyncSession, agent_id: int, start, end) -> Decimal:
    return round_money(
        Decimal(
            (
                await session.execute(
                    select(func.coalesce(func.sum(Payment.amount_usd), 0)).where(
                        Payment.agent_id == agent_id,
                        Payment.paid_at >= start,
                        Payment.paid_at <= end,
                    )
                )
            ).scalar_one()
            or 0
        )
    )


async def submission_counts(
    session: AsyncSession, agent_id: int, year: int, month: int
) -> dict[str, dict[str, int]]:
    """Tur bo'yicha: tasdiqlangan va kutayotgan sonlar."""
    rows = (
        await session.execute(
            select(ContentSubmission.kind, ContentSubmission.status, func.count())
            .where(
                ContentSubmission.agent_id == agent_id,
                ContentSubmission.period_year == year,
                ContentSubmission.period_month == month,
            )
            .group_by(ContentSubmission.kind, ContentSubmission.status)
        )
    ).all()

    natija = {
        k.value: {"approved": 0, "pending": 0, "rejected": 0} for k in SubmissionKind
    }
    for kind, status, count in rows:
        natija[kind.value][status.value] = int(count or 0)
    return natija


# ------------------------------------------------------------- hisoblash
async def salary(
    session: AsyncSession, agent: User, year: int | None = None, month: int | None = None
) -> dict:
    """Menejerning shu oylik ish haqi — jonli, kun sayin yangilanadi."""
    today = today_local()
    year = year or today.year
    month = month or today.month
    start, end = month_bounds(year, month)

    tashrif = await _visit_count(session, agent.id, start, end)
    yigim = await _collected(session, agent.id, start, end)
    sonlar = await submission_counts(session, agent.id, year, month)

    post_soni = sonlar[SubmissionKind.POST.value]["approved"]
    otziv_soni = sonlar[SubmissionKind.REVIEW.value]["approved"]

    yigim_pul, foiz = collection_pay(yigim)

    qismlar = [
        KpiRow(
            key="fiksa",
            label="Oylik fiksa",
            fact=0.0,
            target=0.0,
            amount_usd=FIKSA_USD,
            note="Doimiy qism",
        ),
        KpiRow(
            key="visits",
            label="Klinika tashriflari",
            fact=float(tashrif),
            target=float(TASHRIF_MAQSAD),
            amount_usd=visit_pay(tashrif),
            note=(
                f"{TASHRIF_MAQSAD} ta = ${TASHRIF_BONUS_USD}. "
                f"Kam bo'lsa nisbatan, ko'p bo'lsa ${TASHRIF_BONUS_USD} da to'xtaydi"
            ),
        ),
        KpiRow(
            key="collection",
            label="Yig'ilgan pul",
            fact=float(yigim),
            target=float(YIGIM_CHEGARA_USD),
            amount_usd=yigim_pul,
            note=(
                f"{foiz:g}% qo'llandi. "
                f"${YIGIM_CHEGARA_USD} dan oshsa butun summaga "
                f"{YIGIM_YUQORI_FOIZ:g}%"
            ),
        ),
        KpiRow(
            key="posts",
            label="Post / video",
            fact=float(post_soni),
            target=float(POST_MAX),
            amount_usd=content_pay(post_soni),
            note=f"{POST_MIN} tadan boshlab har biri ${POST_NARX_USD}, {POST_MAX} tada to'xtaydi",
        ),
        KpiRow(
            key="reviews",
            label="Shifokor otzivi",
            fact=float(otziv_soni),
            target=float(POST_MAX),
            amount_usd=content_pay(otziv_soni),
            note=f"{POST_MIN} tadan boshlab har biri ${POST_NARX_USD}, {POST_MAX} tada to'xtaydi",
        ),
    ]

    jami = round_money(sum((q.amount_usd for q in qismlar), ZERO))

    return {
        "user_id": agent.id,
        "full_name": agent.full_name,
        "year": year,
        "month": month,
        "total_usd": jami,
        "rows": [asdict(q) for q in qismlar],
        # Tasdiq kutayotgani ham ko'rinsin — menejer nimani kutayotganini bilsin
        "pending": {
            "posts": sonlar[SubmissionKind.POST.value]["pending"],
            "reviews": sonlar[SubmissionKind.REVIEW.value]["pending"],
        },
        # Tasdiqlansa qancha qo'shiladi
        "potential_usd": round_money(
            content_pay(post_soni + sonlar[SubmissionKind.POST.value]["pending"])
            + content_pay(otziv_soni + sonlar[SubmissionKind.REVIEW.value]["pending"])
            - content_pay(post_soni)
            - content_pay(otziv_soni)
        ),
    }


async def all_salaries(
    session: AsyncSession, year: int | None = None, month: int | None = None
) -> list[dict]:
    """Barcha faol agentlar — direktor uchun oylik jadval."""
    agents = (
        await session.execute(
            select(User)
            .where(User.role == Role.AGENT, User.is_active.is_(True))
            .order_by(User.full_name)
        )
    ).scalars().all()
    return [await salary(session, agent, year, month) for agent in agents]
