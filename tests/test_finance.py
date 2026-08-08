"""Valyuta, qarz yoshlanishi va kredit nazorati."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from app.models import MoveKind, OrderSource
from app.services import debt as debt_service, orders as orders_service, stock as stock_service
from app.services.fx import get_rate, set_rate, usd_to_uzs, uzs_to_usd
from app.services.orders import LineInput
from app.services.fx import today_local


async def test_valyuta_konvertatsiyasi():
    assert usd_to_uzs(Decimal("10"), Decimal("12500")) == Decimal("125000.00")
    assert uzs_to_usd(Decimal("125000"), Decimal("12500")) == Decimal("10.00")


async def test_kurs_saqlanadi_va_qaytariladi(session):
    await set_rate(session, Decimal("13000"))
    assert await get_rate(session) == Decimal("13000.00")

    # Kelajakdagi sana uchun ham eng yaqin oldingi kurs olinadi
    tomorrow = today_local() + timedelta(days=1)
    assert await get_rate(session, tomorrow) == Decimal("13000.00")


async def test_hujjat_kursi_qotib_qoladi(session, base_data):
    await set_rate(session, Decimal("12000"))
    await stock_service.apply_move(
        session,
        kind=MoveKind.IN,
        product_id=base_data["implant"].id,
        qty=10,
        to_warehouse_id=base_data["warehouse"].id,
        doc_type="receipt",
        doc_id=1,
    )
    order = await orders_service.create_order(
        session,
        doctor=base_data["doctor"],
        lines=[LineInput(base_data["implant"].id, 1)],
        actor=base_data["agent"],
        source=OrderSource.AGENT,
        warehouse_id=base_data["warehouse"].id,
    )
    assert order.fx_rate == Decimal("12000.00")

    # Kurs o'zgardi — eski hujjat o'zgarmaydi
    await set_rate(session, Decimal("14000"))
    await session.refresh(order)
    assert order.fx_rate == Decimal("12000.00")


async def test_qarz_yoshlanishi(session, base_data):
    await stock_service.apply_move(
        session,
        kind=MoveKind.IN,
        product_id=base_data["implant"].id,
        qty=100,
        to_warehouse_id=base_data["warehouse"].id,
        doc_type="receipt",
        doc_id=1,
    )
    doctor = base_data["doctor"]
    doctor.debt_limit_usd = Decimal("100000")
    # Tarixiy qarzlarni yig'ish uchun kredit blokini vaqtincha o'chiramiz
    doctor.credit_block_override = True
    await session.flush()

    today = today_local()
    offsets = [-100, -70, -40, -10, 20]  # muddatdan o'tgan kunlar
    for offset in offsets:
        order = await orders_service.create_order(
            session,
            doctor=doctor,
            lines=[LineInput(base_data["implant"].id, 1)],
            actor=base_data["agent"],
            source=OrderSource.AGENT,
            warehouse_id=base_data["warehouse"].id,
        )
        await orders_service.approve(session, order, base_data["agent"])
        await orders_service.deliver(session, order, base_data["keeper"])
        order.due_date = today + timedelta(days=offset)
    await session.flush()

    summary = await debt_service.doctor_debt(session, doctor.id, today)
    assert summary.total_usd == Decimal("500.00")
    assert summary.overdue_usd == Decimal("400.00")
    assert summary.not_due_usd == Decimal("100.00")
    assert summary.max_overdue_days == 100
    assert summary.buckets["90+ kun"] == Decimal("100.00")
    assert summary.buckets["61-90 kun"] == Decimal("100.00")
    assert summary.buckets["31-60 kun"] == Decimal("100.00")
    assert summary.buckets["0-30 kun"] == Decimal("100.00")
    assert summary.buckets["muddati kelmagan"] == Decimal("100.00")

    aging = await (await _import_reports()).debt_aging(session, today)
    assert aging["90+ kun"] == Decimal("100.00")
    assert aging["muddati kelmagan"] == Decimal("100.00")


async def _import_reports():
    from app.services import reports

    return reports


async def test_muddati_otgan_qarz_yangi_buyurtmani_bloklaydi(session, base_data):
    await stock_service.apply_move(
        session,
        kind=MoveKind.IN,
        product_id=base_data["implant"].id,
        qty=100,
        to_warehouse_id=base_data["warehouse"].id,
        doc_type="receipt",
        doc_id=1,
    )
    doctor = base_data["doctor"]
    doctor.debt_limit_usd = Decimal("100000")
    await session.flush()

    order = await orders_service.create_order(
        session,
        doctor=doctor,
        lines=[LineInput(base_data["implant"].id, 1)],
        actor=base_data["agent"],
        source=OrderSource.AGENT,
        warehouse_id=base_data["warehouse"].id,
    )
    await orders_service.approve(session, order, base_data["agent"])
    await orders_service.deliver(session, order, base_data["keeper"])
    order.due_date = today_local() - timedelta(days=15)
    await session.flush()

    reason = await debt_service.credit_check(session, doctor, Decimal("50"))
    assert reason is not None and "muddati o'tgan" in reason.lower()

    # Direktor qo'lda ruxsat bersa — blok olib tashlanadi
    doctor.credit_block_override = True
    await session.flush()
    assert await debt_service.credit_check(session, doctor, Decimal("50")) is None
