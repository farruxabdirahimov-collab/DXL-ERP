"""Buyurtmaning to'liq yo'li: yaratish -> tasdiqlash -> yetkazish -> to'lov."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest

from app.models import MoveKind, OrderSource, OrderStatus, PaymentMethod
from app.services import (
    debt as debt_service,
    inventory_ops,
    orders as orders_service,
    payments as payments_service,
    stock as stock_service,
)
from app.services.fx import today_local
from app.services.orders import LineInput, OrderError


async def _fill_stock(session, base_data, qty: int = 50) -> None:
    for product in (base_data["implant"], base_data["cap"]):
        await stock_service.apply_move(
            session,
            kind=MoveKind.IN,
            product_id=product.id,
            qty=qty,
            to_warehouse_id=base_data["warehouse"].id,
            doc_type="receipt",
            doc_id=product.id,
        )


async def test_toliq_oqim_qarz_va_tolov(session, base_data):
    await _fill_stock(session, base_data)
    doctor = base_data["doctor"]
    agent = base_data["agent"]
    keeper = base_data["keeper"]

    order = await orders_service.create_order(
        session,
        doctor=doctor,
        lines=[LineInput(base_data["implant"].id, 3), LineInput(base_data["cap"].id, 2)],
        actor=agent,
        source=OrderSource.AGENT,
        warehouse_id=base_data["warehouse"].id,
    )
    # 3 * 100 + 2 * 15 = 330
    assert order.total_usd == Decimal("330.00")
    assert order.status is OrderStatus.NEW
    assert order.needs_director is False

    await orders_service.approve(session, order, agent)
    assert order.status is OrderStatus.APPROVED
    # Tovar band qilindi, lekin hali ombordan yechilmadi
    assert await stock_service.get_qty(
        session, base_data["warehouse"].id, base_data["implant"].id
    ) == 50
    assert await stock_service.get_available(
        session, base_data["warehouse"].id, base_data["implant"].id
    ) == 47

    await orders_service.deliver(session, order, keeper)
    assert order.status is OrderStatus.DELIVERED
    assert order.due_date == today_local() + timedelta(days=doctor.payment_term_days)
    assert await stock_service.get_qty(
        session, base_data["warehouse"].id, base_data["implant"].id
    ) == 47

    summary = await debt_service.doctor_debt(session, doctor.id)
    assert summary.total_usd == Decimal("330.00")
    assert summary.overdue_usd == Decimal("0.00")

    # 12 500 so'm = 1 USD kursida to'liq to'lov
    payment, advance = await payments_service.create_payment(
        session,
        doctor=doctor,
        amount_uzs=Decimal("330") * Decimal("12500"),
        method=PaymentMethod.CASH,
        actor=base_data["accountant"],
    )
    assert payment.amount_usd == Decimal("330.00")
    assert advance == Decimal("0.00")

    after = await debt_service.doctor_debt(session, doctor.id)
    assert after.total_usd == Decimal("0.00")


async def test_qisman_tolov_eng_eski_qarzdan_yopiladi(session, base_data):
    await _fill_stock(session, base_data, qty=100)
    doctor = base_data["doctor"]

    orders = []
    for _ in range(2):
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
        orders.append(order)

    # Birinchi buyurtmaning muddatini oldinroq qilamiz
    orders[0].due_date = today_local() - timedelta(days=5)
    orders[1].due_date = today_local() + timedelta(days=25)
    await session.flush()

    _, advance = await payments_service.create_payment(
        session,
        doctor=doctor,
        amount_uzs=Decimal("100") * Decimal("12500"),
        method=PaymentMethod.CARD,
        actor=base_data["accountant"],
    )
    assert advance == Decimal("0.00")
    assert orders[0].paid_usd == Decimal("100.00")
    assert orders[1].paid_usd == Decimal("0.00")

    summary = await debt_service.doctor_debt(session, doctor.id)
    assert summary.total_usd == Decimal("100.00")
    assert summary.overdue_usd == Decimal("0.00")


async def test_qarz_limitidan_oshsa_direktor_tasdigi(session, base_data):
    await _fill_stock(session, base_data, qty=100)
    doctor = base_data["doctor"]
    doctor.debt_limit_usd = Decimal("150")
    await session.flush()

    order = await orders_service.create_order(
        session,
        doctor=doctor,
        lines=[LineInput(base_data["implant"].id, 2)],  # 200 USD > 150 limit
        actor=base_data["agent"],
        source=OrderSource.AGENT,
        warehouse_id=base_data["warehouse"].id,
    )
    assert order.needs_director is True
    assert "limit" in (order.director_reason or "").lower()

    # Agent tasdiqlasa — direktor ko'rigiga tushadi
    await orders_service.approve(session, order, base_data["agent"])
    assert order.status is OrderStatus.DIRECTOR_REVIEW

    # Agent ikkinchi marta ham tasdiqlay olmaydi
    with pytest.raises(OrderError, match="direktor"):
        await orders_service.approve(session, order, base_data["agent"])

    await orders_service.approve(session, order, base_data["director"])
    assert order.status is OrderStatus.APPROVED


async def test_chegirma_limitidan_oshsa_direktor_tasdigi(session, base_data):
    from app.services.settings_service import set_setting

    await set_setting(session, "max_discount_pct_agent", 10)
    await _fill_stock(session, base_data)
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
        discount_pct=Decimal("25"),
    )
    assert order.needs_director is True
    assert "chegirma" in (order.director_reason or "").lower()


async def test_bekor_qilinganda_rezerv_bosatiladi(session, base_data):
    await _fill_stock(session, base_data)
    order = await orders_service.create_order(
        session,
        doctor=base_data["doctor"],
        lines=[LineInput(base_data["implant"].id, 5)],
        actor=base_data["agent"],
        source=OrderSource.AGENT,
        warehouse_id=base_data["warehouse"].id,
    )
    await orders_service.approve(session, order, base_data["agent"])
    assert await stock_service.get_available(
        session, base_data["warehouse"].id, base_data["implant"].id
    ) == 45

    await orders_service.cancel(session, order, base_data["director"], "Vrach voz kechdi")
    assert await stock_service.get_available(
        session, base_data["warehouse"].id, base_data["implant"].id
    ) == 50


async def test_qaytarish_qarzni_kamaytiradi(session, base_data):
    await _fill_stock(session, base_data)
    doctor = base_data["doctor"]

    order = await orders_service.create_order(
        session,
        doctor=doctor,
        lines=[LineInput(base_data["implant"].id, 4)],
        actor=base_data["agent"],
        source=OrderSource.AGENT,
        warehouse_id=base_data["warehouse"].id,
    )
    await orders_service.approve(session, order, base_data["agent"])
    await orders_service.deliver(session, order, base_data["keeper"])
    assert order.total_usd == Decimal("400.00")

    doc = await inventory_ops.create_return(
        session,
        doctor=doctor,
        warehouse_id=base_data["warehouse"].id,
        lines=[(base_data["implant"].id, 1)],
        actor=base_data["keeper"],
        order_id=order.id,
        reason="Qadoq shikastlangan",
    )
    assert doc.total_usd == Decimal("100.00")
    assert order.returned_usd == Decimal("100.00")

    summary = await debt_service.doctor_debt(session, doctor.id)
    assert summary.total_usd == Decimal("300.00")
    # Tovar omborga qaytdi
    assert await stock_service.get_qty(
        session, base_data["warehouse"].id, base_data["implant"].id
    ) == 47


async def test_yetkazilgandan_keyin_bekor_qilib_bolmaydi(session, base_data):
    await _fill_stock(session, base_data)
    order = await orders_service.create_order(
        session,
        doctor=base_data["doctor"],
        lines=[LineInput(base_data["implant"].id, 1)],
        actor=base_data["agent"],
        source=OrderSource.AGENT,
        warehouse_id=base_data["warehouse"].id,
    )
    await orders_service.approve(session, order, base_data["agent"])
    await orders_service.deliver(session, order, base_data["keeper"])

    with pytest.raises(OrderError, match="qaytarish"):
        await orders_service.cancel(session, order, base_data["director"])


async def test_inventarizatsiya_farqni_yozadi(session, base_data):
    await _fill_stock(session, base_data, qty=20)
    delta = await inventory_ops.adjust_stock(
        session,
        warehouse_id=base_data["warehouse"].id,
        product_id=base_data["implant"].id,
        new_qty=17,
        actor=base_data["keeper"],
        note="Yillik inventarizatsiya",
    )
    assert delta == -3
    assert await stock_service.get_qty(
        session, base_data["warehouse"].id, base_data["implant"].id
    ) == 17
