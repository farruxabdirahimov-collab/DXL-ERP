"""Sodiqlik, A/B/C toifalar va reja bajarilishi."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from app.models import DoctorCategory
from app.services.loyalty import (
    DoctorMetrics,
    assign_categories,
    loyalty_score,
    upcoming_birthdays_filter,
)
from app.services.plans import Metric, expected_pace_pct, previous_month


def _metrics(**kwargs) -> DoctorMetrics:
    base = DoctorMetrics(
        purchased_12m_usd=Decimal("0"),
        orders_12m=0,
        total_purchased_usd=Decimal("0"),
        last_order_at=None,
        avg_payment_delay_days=0.0,
    )
    for key, value in kwargs.items():
        setattr(base, key, value)
    return base


def test_ideal_mijoz_yuqori_ball_oladi():
    today = date(2026, 8, 8)
    metrics = _metrics(
        purchased_12m_usd=Decimal("10000"),
        orders_12m=12,
        last_order_at=datetime(2026, 8, 7, tzinfo=timezone.utc),
        avg_payment_delay_days=0.0,
    )
    score = loyalty_score(
        metrics, reference_amount_usd=Decimal("10000"), on_date=today
    )
    assert score >= 98


def test_yomon_mijoz_past_ball_oladi():
    today = date(2026, 8, 8)
    metrics = _metrics(
        purchased_12m_usd=Decimal("100"),
        orders_12m=1,
        last_order_at=datetime(2025, 9, 1, tzinfo=timezone.utc),
        avg_payment_delay_days=45.0,
    )
    score = loyalty_score(
        metrics, reference_amount_usd=Decimal("10000"), on_date=today
    )
    assert score <= 10


def test_xarid_qilmagan_mijoz_nol():
    assert (
        loyalty_score(
            _metrics(avg_payment_delay_days=30.0),
            reference_amount_usd=Decimal("1000"),
            on_date=date(2026, 8, 8),
        )
        == 0
    )


def test_abc_toifalar_ulushi():
    ranked = list(range(1, 11))  # 10 ta vrach, kamayish tartibida
    result = assign_categories(ranked, a_pct=20, b_pct=50)
    assert [result[i] for i in ranked[:2]] == [DoctorCategory.A, DoctorCategory.A]
    assert [result[i] for i in ranked[2:5]] == [DoctorCategory.B] * 3
    assert [result[i] for i in ranked[5:]] == [DoctorCategory.C] * 5


def test_abc_bitta_mijoz_bilan():
    result = assign_categories([7], a_pct=20, b_pct=50)
    assert result == {7: DoctorCategory.A}


def test_abc_bosh_royxat():
    assert assign_categories([], a_pct=20, b_pct=50) == {}


def test_tugilgan_kunlar_filtri():
    class FakeDoctor:
        def __init__(self, birth_date):
            self.birth_date = birth_date

    today = date(2026, 8, 8)
    bugun = FakeDoctor(date(1980, 8, 8))
    uch_kundan = FakeDoctor(date(1975, 8, 11))
    keyingi_oy = FakeDoctor(date(1990, 9, 20))
    yoq = FakeDoctor(None)

    result = upcoming_birthdays_filter([bugun, uch_kundan, keyingi_oy, yoq], today, 3)
    assert result == [bugun, uch_kundan]


def test_yil_oxiridagi_tugilgan_kun():
    class FakeDoctor:
        def __init__(self, birth_date):
            self.birth_date = birth_date

    # 30-dekabrdan 3 kun ichida 1-yanvar ham tushadi
    doctor = FakeDoctor(date(1988, 1, 1))
    result = upcoming_birthdays_filter([doctor], date(2026, 12, 30), 3)
    assert result == [doctor]


def test_reja_foizi():
    assert Metric.build(50, 100).pct == 50.0
    assert Metric.build(120, 100).pct == 120.0
    # Reja qo'yilmagan bo'lsa 0 ga bo'linmaydi
    assert Metric.build(50, 0).pct == 0.0


def test_kutilgan_temp():
    assert expected_pace_pct(15, 30) == 50.0
    assert expected_pace_pct(0, 31) == 0.0
    assert expected_pace_pct(31, 31) == 100.0


def test_oldingi_oy():
    assert previous_month(2026, 1) == (2025, 12)
    assert previous_month(2026, 8) == (2026, 7)
