"""Menejer KPI: ish haqi avtomatik hisoblanishi."""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models import (
    ContentSubmission,
    PaymentMethod,
    Role,
    SubmissionKind,
    SubmissionStatus,
    User,
    Visit,
    utcnow,
)
from app.services import kpi
from app.services.fx import today_local


# --------------------------------------------------------------- formulalar
@pytest.mark.parametrize(
    "tashrif,kutilgan",
    [(0, "0"), (1, "0.60"), (125, "75.00"), (200, "120.00"), (250, "150.00"),
     (300, "150.00")],
)
def test_tashrif_haqqi(tashrif, kutilgan):
    """250 ta = $150, kam bo'lsa nisbatan, ko'p bo'lsa oshmaydi."""
    assert kpi.visit_pay(tashrif) == Decimal(kutilgan)


@pytest.mark.parametrize(
    "yigim,kutilgan,foiz",
    [
        ("0", "0", "2.5"),
        ("1000", "25.00", "2.5"),
        ("3999", "99.98", "2.5"),
        ("4000", "120.00", "3"),   # chegarada butun summaga 3%
        ("5000", "150.00", "3"),
    ],
)
def test_yigim_bonusi(yigim, kutilgan, foiz):
    summa, qollangan = kpi.collection_pay(Decimal(yigim))
    assert summa == Decimal(kutilgan)
    assert qollangan == Decimal(foiz)


def test_chegarani_kesib_otish_foydali():
    """$3999 dan $4000 ga o'tish sezilarli farq bersin — rag'bat shu."""
    past, _ = kpi.collection_pay(Decimal("3999"))
    yuqori, _ = kpi.collection_pay(Decimal("4000"))
    assert yuqori - past > Decimal("20")


@pytest.mark.parametrize(
    "soni,kutilgan",
    [(0, "0"), (4, "0"), (5, "25.00"), (10, "50.00"), (11, "55.00"),
     (12, "60.00"), (13, "60.00"), (25, "60.00")],
)
def test_post_haqqi(soni, kutilgan):
    """4 tagacha to'lanmaydi, 5-12 har biri $5, 12 dan keyin oshmaydi."""
    assert kpi.content_pay(soni) == Decimal(kutilgan)


# ------------------------------------------------------------ to'liq hisob
async def _tashrif(session, agent, soni):
    for _ in range(soni):
        session.add(Visit(created_at=utcnow(), agent_id=agent.id, doctor_id=1))
    await session.flush()


async def _yuborma(session, agent, kind, soni, status=SubmissionStatus.APPROVED):
    bugun = today_local()
    for i in range(soni):
        session.add(
            ContentSubmission(
                agent_id=agent.id,
                kind=kind,
                url=f"https://t.me/dxl/{kind.value}{i}",
                status=status,
                period_year=bugun.year,
                period_month=bugun.month,
            )
        )
    await session.flush()


async def test_boshlangich_oylik_faqat_fiksa(session, base_data):
    r = await kpi.salary(session, base_data["agent"])
    assert r["total_usd"] == Decimal("200.00")
    qismlar = {q["key"]: q for q in r["rows"]}
    assert qismlar["fiksa"]["amount_usd"] == Decimal("200")
    assert qismlar["visits"]["amount_usd"] == Decimal("0")


async def test_toliq_oylik_hisoblanadi(session, base_data):
    """Barcha KPI bajarilgan menejer: 200 + 150 + 3% + 60 + 60."""
    from app.services import payments as payments_service

    agent = base_data["agent"]
    await _tashrif(session, agent, 250)
    await _yuborma(session, agent, SubmissionKind.POST, 12)
    await _yuborma(session, agent, SubmissionKind.REVIEW, 12)

    # $5000 yig'ildi -> 3% = $150
    await payments_service.create_payment(
        session, doctor=base_data["doctor"],
        amount_uzs=Decimal("63250000"), fx_rate=Decimal("12650"),
        method=PaymentMethod.CASH, actor=base_data["accountant"],
    )

    r = await kpi.salary(session, agent)
    qismlar = {q["key"]: q["amount_usd"] for q in r["rows"]}
    assert qismlar["fiksa"] == Decimal("200")
    assert qismlar["visits"] == Decimal("150.00")
    assert qismlar["collection"] == Decimal("150.00")
    assert qismlar["posts"] == Decimal("60.00")
    assert qismlar["reviews"] == Decimal("60.00")
    assert r["total_usd"] == Decimal("620.00")


async def test_faqat_tasdiqlangan_post_sanaladi(session, base_data):
    """Tasdiqlanmagani pulga kirmaydi, lekin menejer uni ko'rib turadi."""
    agent = base_data["agent"]
    await _yuborma(session, agent, SubmissionKind.POST, 5)
    await _yuborma(session, agent, SubmissionKind.POST, 3, SubmissionStatus.PENDING)
    await _yuborma(session, agent, SubmissionKind.POST, 2, SubmissionStatus.REJECTED)

    r = await kpi.salary(session, agent)
    qismlar = {q["key"]: q for q in r["rows"]}
    assert qismlar["posts"]["amount_usd"] == Decimal("25.00"), "faqat 5 tasi"
    assert r["pending"]["posts"] == 3
    # 3 tasi tasdiqlansa 8 ta bo'ladi -> $40, ya'ni +$15
    assert r["potential_usd"] == Decimal("15.00")


async def test_tasdiqlash_oylikni_oshiradi(session, base_data):
    from app.api.kpi import review_submission
    from app.schemas import SubmissionReviewIn

    agent = base_data["agent"]
    await _yuborma(session, agent, SubmissionKind.POST, 5)
    await _yuborma(session, agent, SubmissionKind.POST, 1, SubmissionStatus.PENDING)

    oldin = (await kpi.salary(session, agent))["total_usd"]

    kutayotgan = (
        await session.execute(
            __import__("sqlalchemy").select(ContentSubmission).where(
                ContentSubmission.status == SubmissionStatus.PENDING
            )
        )
    ).scalars().one()
    await review_submission(
        kutayotgan.id, SubmissionReviewIn(approve=True), session, base_data["director"]
    )

    keyin = (await kpi.salary(session, agent))["total_usd"]
    assert keyin - oldin == Decimal("5.00")


async def test_rad_etilgani_pulga_kirmaydi(session, base_data):
    from app.api.kpi import review_submission
    from app.schemas import SubmissionReviewIn

    agent = base_data["agent"]
    await _yuborma(session, agent, SubmissionKind.POST, 6)
    oldin = (await kpi.salary(session, agent))["total_usd"]

    birinchi = (
        await session.execute(
            __import__("sqlalchemy").select(ContentSubmission).limit(1)
        )
    ).scalars().one()
    await review_submission(
        birinchi.id,
        SubmissionReviewIn(approve=False, reason="Sifatsiz video"),
        session,
        base_data["director"],
    )

    keyin = (await kpi.salary(session, agent))["total_usd"]
    assert keyin - oldin == Decimal("-5.00")
    await session.refresh(birinchi)
    assert birinchi.reject_reason == "Sifatsiz video"


async def test_menejer_ozganing_yozuvini_ochira_olmaydi(session, base_data):
    from app.api.kpi import delete_submission

    ozga = User(full_name="Boshqa menejer", role=Role.AGENT, telegram_id=882001)
    session.add(ozga)
    await session.flush()
    await _yuborma(session, base_data["agent"], SubmissionKind.POST, 1,
                   SubmissionStatus.PENDING)

    row = (
        await session.execute(__import__("sqlalchemy").select(ContentSubmission))
    ).scalars().one()

    with pytest.raises(HTTPException) as exc:
        await delete_submission(row.id, session, ozga)
    assert exc.value.status_code == 403


async def test_tasdiqlangan_yozuvni_menejer_ochira_olmaydi(session, base_data):
    from app.api.kpi import delete_submission

    await _yuborma(session, base_data["agent"], SubmissionKind.POST, 1)
    row = (
        await session.execute(__import__("sqlalchemy").select(ContentSubmission))
    ).scalars().one()

    with pytest.raises(HTTPException, match="Tasdiqlangan"):
        await delete_submission(row.id, session, base_data["agent"])

    # Direktor o'chira oladi
    r = await delete_submission(row.id, session, base_data["director"])
    assert r.ok


async def test_yuborma_joylangan_oyga_hisoblanadi(session, base_data):
    """Direktor kech tasdiqlasa ham oy o'zgarmaydi."""
    from app.api.kpi import create_submission
    from app.schemas import SubmissionIn

    bugun = today_local()
    await create_submission(
        SubmissionIn(kind="post", url="https://t.me/dxl/1"),
        session,
        base_data["agent"],
    )
    row = (
        await session.execute(__import__("sqlalchemy").select(ContentSubmission))
    ).scalars().one()
    assert (row.period_year, row.period_month) == (bugun.year, bugun.month)
    assert row.status is SubmissionStatus.PENDING
