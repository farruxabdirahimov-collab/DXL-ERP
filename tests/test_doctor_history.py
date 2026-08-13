"""Vrach kartochkasidagi mini hisobot: xarid, razmer, qaytarish, to'lov."""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models import MoveKind, OrderSource, PaymentMethod, Role, User
from app.services import doctor_history, inventory_ops
from app.services import orders as orders_service, stock as stock_service
from app.services.orders import LineInput


async def _stock(session, base_data, product, qty=50):
    await stock_service.apply_move(
        session,
        kind=MoveKind.IN,
        product_id=product.id,
        qty=qty,
        to_warehouse_id=base_data["warehouse"].id,
        doc_type="receipt",
        doc_id=product.id,
    )


async def _deliver(session, base_data, lines):
    order = await orders_service.create_order(
        session,
        doctor=base_data["doctor"],
        lines=lines,
        actor=base_data["agent"],
        source=OrderSource.AGENT,
        warehouse_id=base_data["warehouse"].id,
    )
    order.needs_director = False
    await orders_service.approve(session, order, base_data["agent"])
    await orders_service.deliver(session, order, base_data["keeper"])
    return order


async def test_bosh_vrachda_hisobot_bosh_boladi(session, base_data):
    data = await doctor_history.build(session, base_data["doctor"].id)
    assert data["summary"]["orders_count"] == 0
    assert data["summary"]["net_usd"] == Decimal("0.00")
    assert data["sizes"] == []
    assert data["timeline"] == []


async def test_qaysi_razmerlarni_oldi_va_qaytardi(session, base_data):
    implant = base_data["implant"]
    cap = base_data["cap"]
    await _stock(session, base_data, implant)
    await _stock(session, base_data, cap)

    order = await _deliver(
        session,
        base_data,
        [LineInput(implant.id, 6), LineInput(cap.id, 2)],
    )
    await inventory_ops.create_return(
        session,
        doctor=base_data["doctor"],
        warehouse_id=base_data["warehouse"].id,
        lines=[(implant.id, 2)],
        actor=base_data["agent"],
        order_id=order.id,
        reason="Razmer mos kelmadi",
    )

    data = await doctor_history.build(session, base_data["doctor"].id)

    rows = {r["size"]: r for r in data["sizes"]}
    assert implant.size_label in rows
    olingan = rows[implant.size_label]
    assert olingan["bought_qty"] == 6
    assert olingan["returned_qty"] == 2
    assert olingan["net_qty"] == 4, "sof dona ko'rinishi kerak"

    # Qaytarilmagan mahsulotda qaytarish nolga teng
    assert rows[cap.size_label]["returned_qty"] == 0
    assert rows[cap.size_label]["net_qty"] == 2


async def test_tortta_korsatkich_mos_keladi(session, base_data):
    from app.services import payments as payments_service

    implant = base_data["implant"]
    await _stock(session, base_data, implant)
    order = await _deliver(session, base_data, [LineInput(implant.id, 5)])  # $500

    await inventory_ops.create_return(
        session,
        doctor=base_data["doctor"],
        warehouse_id=base_data["warehouse"].id,
        lines=[(implant.id, 1)],
        actor=base_data["agent"],
        order_id=order.id,
        reason="Ortiqcha",
    )
    await payments_service.create_payment(
        session,
        doctor=base_data["doctor"],
        amount_uzs=Decimal("1265000"),
        fx_rate=Decimal("12650"),  # -> $100
        method=PaymentMethod.CASH,
        actor=base_data["accountant"],
    )

    s = (await doctor_history.build(session, base_data["doctor"].id))["summary"]

    assert s["bought_usd"] == Decimal("500.00")
    assert s["returned_usd"] == Decimal("100.00")
    assert s["net_usd"] == Decimal("400.00")
    assert s["paid_usd"] == Decimal("100.00")
    assert s["debt_usd"] == Decimal("300.00"), "sof xarid − to'lov"
    assert s["bought_units"] == 5
    assert s["returned_units"] == 1
    assert s["net_units"] == 4


async def test_tarixda_uch_xil_voqea_ham_boladi(session, base_data):
    from app.services import payments as payments_service

    implant = base_data["implant"]
    await _stock(session, base_data, implant)
    order = await _deliver(session, base_data, [LineInput(implant.id, 3)])
    await inventory_ops.create_return(
        session,
        doctor=base_data["doctor"],
        warehouse_id=base_data["warehouse"].id,
        lines=[(implant.id, 1)],
        actor=base_data["agent"],
        order_id=order.id,
        reason="Qadoq shikast",
    )
    await payments_service.create_payment(
        session,
        doctor=base_data["doctor"],
        amount_uzs=Decimal("1265000"),
        fx_rate=Decimal("12650"),
        method=PaymentMethod.CASH,
        actor=base_data["accountant"],
    )

    timeline = (await doctor_history.build(session, base_data["doctor"].id))["timeline"]
    kinds = [e["kind"] for e in timeline]
    assert set(kinds) == {"order", "return", "payment"}

    xarid = next(e for e in timeline if e["kind"] == "order")
    assert xarid["lines"][0]["size"] == implant.size_label
    assert xarid["lines"][0]["qty"] == 3

    qaytarish = next(e for e in timeline if e["kind"] == "return")
    assert qaytarish["note"] == "Qadoq shikast"
    assert qaytarish["lines"][0]["qty"] == 1

    tolov = next(e for e in timeline if e["kind"] == "payment")
    assert "so'm" in tolov["note"]


async def test_agent_ozga_vrachning_tarixini_kormaydi(session, base_data):
    from app.api.doctors import doctor_history as endpoint

    ozga = User(full_name="Boshqa agent", role=Role.AGENT, telegram_id=880555)
    session.add(ozga)
    await session.flush()

    with pytest.raises(HTTPException) as exc:
        await endpoint(base_data["doctor"].id, session, ozga)
    assert exc.value.status_code == 403

    # O'z agenti ko'radi
    natija = await endpoint(base_data["doctor"].id, session, base_data["agent"])
    assert "summary" in natija
