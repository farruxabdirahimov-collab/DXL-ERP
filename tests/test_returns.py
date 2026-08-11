"""Qaytarish (vozvrat) va uning hisobotlarga ta'siri.

Asosiy talab: qaytarilgan tovar hech qayerda "sotilgan" bo'lib qolmasligi
kerak — na sotuv summasida, na mahsulot tahlilida, na agent rejasida,
na vrachning xarid darajasida.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.models import MoveKind, OrderSource, Return, Role
from app.permissions import RETURNS_CREATE, can
from app.services import inventory_ops, orders as orders_service, stock as stock_service
from app.services.inventory_ops import InventoryOpError
from app.services.orders import LineInput


async def _sell(session, base_data, qty: int = 5, stock: int = 50):
    """Tovar kiritib, yetkazilgan buyurtma yaratadi."""
    await stock_service.apply_move(
        session,
        kind=MoveKind.IN,
        product_id=base_data["implant"].id,
        qty=stock,
        to_warehouse_id=base_data["warehouse"].id,
        doc_type="receipt",
        doc_id=base_data["implant"].id,
    )
    order = await orders_service.create_order(
        session,
        doctor=base_data["doctor"],
        lines=[LineInput(base_data["implant"].id, qty)],
        actor=base_data["agent"],
        source=OrderSource.AGENT,
        warehouse_id=base_data["warehouse"].id,
    )
    await orders_service.approve(session, order, base_data["agent"])
    await orders_service.deliver(session, order, base_data["keeper"])
    return order


def test_agent_qaytarish_qila_oladi():
    assert can(Role.AGENT, RETURNS_CREATE)
    assert can(Role.WAREHOUSE, RETURNS_CREATE)
    assert can(Role.ACCOUNTANT, RETURNS_CREATE)
    # Vrach va ta'sischi qila olmaydi
    assert not can(Role.DOCTOR, RETURNS_CREATE)
    assert not can(Role.FOUNDER, RETURNS_CREATE)


async def test_qaytarish_agentga_boglanadi(session, base_data):
    order = await _sell(session, base_data, qty=4)
    doc = await inventory_ops.create_return(
        session,
        doctor=base_data["doctor"],
        warehouse_id=base_data["warehouse"].id,
        lines=[(base_data["implant"].id, 1)],
        actor=base_data["keeper"],
        order_id=order.id,
        reason="Qadoq shikastlangan",
    )
    # Omborchi rasmiylashtirsa ham, hisobot buyurtma agentiga yoziladi
    assert doc.agent_id == base_data["agent"].id


async def test_sotuvdan_ayiriladi(session, base_data):
    """Sotuv hisoboti sof raqamni ko'rsatishi kerak."""
    from app.services import reports as rp
    from app.services.fx import today_local

    order = await _sell(session, base_data, qty=5)  # 5 x 100 = 500
    day = today_local()
    start, end = rp.day_bounds(day)

    before = await rp.sales_summary(session, start, end)
    assert before["amount_usd"] == Decimal("500.00")
    assert before["units"] == 5

    await inventory_ops.create_return(
        session,
        doctor=base_data["doctor"],
        warehouse_id=base_data["warehouse"].id,
        lines=[(base_data["implant"].id, 2)],
        actor=base_data["agent"],
        order_id=order.id,
        reason="Ortiqcha olingan",
    )

    after = await rp.sales_summary(session, start, end)
    assert after["amount_usd"] == Decimal("300.00"), "sof sotuv 500 - 200"
    assert after["units"] == 3
    # Batafsil ko'rsatkichlar ham mavjud
    assert after["gross_amount_usd"] == Decimal("500.00")
    assert after["returned_usd"] == Decimal("200.00")
    assert after["returned_units"] == 2
    assert after["returns_count"] == 1


async def test_mahsulot_tahlilidan_ayiriladi(session, base_data):
    from app.services import reports as rp
    from app.services.fx import today_local

    order = await _sell(session, base_data, qty=6)
    start, end = rp.day_bounds(today_local())

    top = await rp.top_products(session, start, end, limit=10)
    assert top[0]["qty"] == 6

    await inventory_ops.create_return(
        session,
        doctor=base_data["doctor"],
        warehouse_id=base_data["warehouse"].id,
        lines=[(base_data["implant"].id, 4)],
        actor=base_data["agent"],
        order_id=order.id,
        reason="Mos kelmadi",
    )

    top = await rp.top_products(session, start, end, limit=10)
    assert top[0]["qty"] == 2, "eng ko'p sotilganda faqat sof dona ko'rinishi kerak"
    assert top[0]["returned_qty"] == 4

    sizes = await rp.size_demand(session, start, end)
    assert sizes[0]["qty"] == 2, "razmer talabi ham sof bo'lishi kerak"


async def test_agent_rejasidan_ayiriladi(session, base_data):
    from app.services import plans as plans_service
    from app.services.fx import today_local

    order = await _sell(session, base_data, qty=5)
    day = today_local()
    start, end = plans_service.month_bounds(day.year, day.month)

    amount, units, _ = await plans_service.agent_facts(
        session, base_data["agent"].id, start, end
    )
    assert amount == Decimal("500.00")
    assert units == 5

    await inventory_ops.create_return(
        session,
        doctor=base_data["doctor"],
        warehouse_id=base_data["warehouse"].id,
        lines=[(base_data["implant"].id, 3)],
        actor=base_data["agent"],
        order_id=order.id,
        reason="Vrach qaytardi",
    )

    amount, units, _ = await plans_service.agent_facts(
        session, base_data["agent"].id, start, end
    )
    assert amount == Decimal("200.00"), "reja bajarilishi shishib qolmasligi kerak"
    assert units == 2


async def test_vrachning_xarid_darajasi_kamayadi(session, base_data):
    from app.services import loyalty
    from app.services.fx import today_local

    order = await _sell(session, base_data, qty=5)
    doctor = base_data["doctor"]
    assert doctor.total_purchased_usd == Decimal("500.00")

    await inventory_ops.create_return(
        session,
        doctor=doctor,
        warehouse_id=base_data["warehouse"].id,
        lines=[(base_data["implant"].id, 2)],
        actor=base_data["agent"],
        order_id=order.id,
        reason="Qaytarildi",
    )
    assert doctor.total_purchased_usd == Decimal("300.00")

    # Kechki qayta hisobda ham sof qiymat chiqadi
    await loyalty.recalculate(session, today_local())
    await session.refresh(doctor)
    assert doctor.purchased_12m_usd == Decimal("300.00")


async def test_qarz_va_ombor_bir_vaqtda_tuzatiladi(session, base_data):
    from app.services import debt as debt_service

    order = await _sell(session, base_data, qty=5, stock=20)
    assert await stock_service.get_qty(
        session, base_data["warehouse"].id, base_data["implant"].id
    ) == 15

    summary = await debt_service.doctor_debt(session, base_data["doctor"].id)
    assert summary.total_usd == Decimal("500.00")

    await inventory_ops.create_return(
        session,
        doctor=base_data["doctor"],
        warehouse_id=base_data["warehouse"].id,
        lines=[(base_data["implant"].id, 2)],
        actor=base_data["agent"],
        order_id=order.id,
        reason="Qaytarish",
    )

    # Tovar omborga qaytdi
    assert await stock_service.get_qty(
        session, base_data["warehouse"].id, base_data["implant"].id
    ) == 17
    # Qarz kamaydi
    summary = await debt_service.doctor_debt(session, base_data["doctor"].id)
    assert summary.total_usd == Decimal("300.00")


async def test_sotilganidan_kop_qaytarib_bolmaydi(session, base_data):
    order = await _sell(session, base_data, qty=3)
    with pytest.raises(InventoryOpError, match="ko'p"):
        await inventory_ops.create_return(
            session,
            doctor=base_data["doctor"],
            warehouse_id=base_data["warehouse"].id,
            lines=[(base_data["implant"].id, 5)],
            actor=base_data["agent"],
            order_id=order.id,
            reason="Xato",
        )


async def test_buyurtmada_yoq_mahsulot_qaytarilmaydi(session, base_data):
    order = await _sell(session, base_data, qty=2)
    with pytest.raises(InventoryOpError, match="yo'q"):
        await inventory_ops.create_return(
            session,
            doctor=base_data["doctor"],
            warehouse_id=base_data["warehouse"].id,
            lines=[(base_data["cap"].id, 1)],
            actor=base_data["agent"],
            order_id=order.id,
            reason="Xato",
        )


async def test_sababsiz_qaytarish_yozilmaydi(session, base_data):
    """Sabab bo'sh bo'lsa ham hujjat yaratiladi, lekin bo'sh ro'yxat rad etiladi."""
    await _sell(session, base_data, qty=2)
    with pytest.raises(InventoryOpError, match="bo'sh"):
        await inventory_ops.create_return(
            session,
            doctor=base_data["doctor"],
            warehouse_id=base_data["warehouse"].id,
            lines=[],
            actor=base_data["agent"],
            reason="Sabab",
        )


async def test_kunlik_hisobotda_qaytarish_ochiq_korsatiladi(session, base_data):
    """21:00 xabarida raqam nega kamayganini o'qib bilish mumkin bo'lsin."""
    from app.jobs.daily_report import build_agent_report, build_management_report
    from app.services.fx import today_local

    order = await _sell(session, base_data, qty=5)
    day = today_local()

    matn = await build_management_report(session, day)
    assert "Qaytarildi" not in matn, "qaytarish bo'lmasa ortiqcha qator chiqmasin"

    await inventory_ops.create_return(
        session,
        doctor=base_data["doctor"],
        warehouse_id=base_data["warehouse"].id,
        lines=[(base_data["implant"].id, 2)],
        actor=base_data["agent"],
        order_id=order.id,
        reason="Qaytarildi",
    )

    matn = await build_management_report(session, day)
    assert "Qaytarildi" in matn
    assert "$300" in matn, "sof sotuv ko'rinishi kerak"

    agent_matn = await build_agent_report(session, base_data["agent"], day)
    assert "Qaytarildi" in agent_matn


async def test_qaytarish_narxi_sotilgan_narxda_hisoblanadi(session, base_data):
    """Chegirma bilan sotilgan bo'lsa, qaytarish ham o'sha narxda."""
    await stock_service.apply_move(
        session,
        kind=MoveKind.IN,
        product_id=base_data["implant"].id,
        qty=20,
        to_warehouse_id=base_data["warehouse"].id,
        doc_type="receipt",
        doc_id=1,
    )
    order = await orders_service.create_order(
        session,
        doctor=base_data["doctor"],
        lines=[LineInput(base_data["implant"].id, 4, Decimal("25"))],  # 25% chegirma
        actor=base_data["agent"],
        source=OrderSource.AGENT,
        warehouse_id=base_data["warehouse"].id,
    )
    order.needs_director = False
    await orders_service.approve(session, order, base_data["director"])
    await orders_service.deliver(session, order, base_data["keeper"])
    assert order.total_usd == Decimal("300.00")  # 4 x 100 x 0.75

    doc = await inventory_ops.create_return(
        session,
        doctor=base_data["doctor"],
        warehouse_id=base_data["warehouse"].id,
        lines=[(base_data["implant"].id, 2)],
        actor=base_data["agent"],
        order_id=order.id,
        reason="Yarmi qaytdi",
    )
    # To'liq narxda emas, chegirmali narxda: 2 x 75
    assert doc.total_usd == Decimal("150.00")
