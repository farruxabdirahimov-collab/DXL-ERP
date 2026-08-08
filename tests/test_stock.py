"""Ombor qoldig'i matematikasi."""

from __future__ import annotations

import pytest

from app.models import MoveKind, Stock, WarehouseKind, Warehouse
from app.services import stock as stock_service
from app.services.stock import MoveLine, StockError


async def test_kirim_qoldiqni_oshiradi(session, base_data):
    warehouse = base_data["warehouse"]
    product = base_data["implant"]

    await stock_service.apply_move(
        session,
        kind=MoveKind.IN,
        product_id=product.id,
        qty=25,
        to_warehouse_id=warehouse.id,
        doc_type="receipt",
        doc_id=1,
    )
    assert await stock_service.get_qty(session, warehouse.id, product.id) == 25


async def test_yetarli_bolmasa_chiqim_rad_etiladi(session, base_data):
    warehouse = base_data["warehouse"]
    product = base_data["implant"]

    await stock_service.apply_move(
        session,
        kind=MoveKind.IN,
        product_id=product.id,
        qty=3,
        to_warehouse_id=warehouse.id,
        doc_type="receipt",
        doc_id=1,
    )
    with pytest.raises(StockError, match="yetarli emas"):
        await stock_service.apply_move(
            session,
            kind=MoveKind.WRITEOFF,
            product_id=product.id,
            qty=5,
            from_warehouse_id=warehouse.id,
            doc_type="writeoff",
            doc_id=1,
        )
    assert await stock_service.get_qty(session, warehouse.id, product.id) == 3


async def test_rezerv_bosh_qoldiqni_kamaytiradi(session, base_data):
    warehouse = base_data["warehouse"]
    product = base_data["implant"]

    await stock_service.apply_move(
        session,
        kind=MoveKind.IN,
        product_id=product.id,
        qty=10,
        to_warehouse_id=warehouse.id,
        doc_type="receipt",
        doc_id=1,
    )
    await stock_service.reserve(session, warehouse.id, [MoveLine(product.id, 4)])

    assert await stock_service.get_qty(session, warehouse.id, product.id) == 10
    assert await stock_service.get_available(session, warehouse.id, product.id) == 6

    # Band qilingan tovardan ortiqcha rezerv qilib bo'lmaydi
    with pytest.raises(StockError, match="yetarli emas"):
        await stock_service.reserve(session, warehouse.id, [MoveLine(product.id, 7)])


async def test_band_tovarni_spisaniye_qilib_bolmaydi(session, base_data):
    warehouse = base_data["warehouse"]
    product = base_data["implant"]

    await stock_service.apply_move(
        session,
        kind=MoveKind.IN,
        product_id=product.id,
        qty=10,
        to_warehouse_id=warehouse.id,
        doc_type="receipt",
        doc_id=1,
    )
    await stock_service.reserve(session, warehouse.id, [MoveLine(product.id, 8)])

    with pytest.raises(StockError, match="band"):
        await stock_service.apply_move(
            session,
            kind=MoveKind.WRITEOFF,
            product_id=product.id,
            qty=5,
            from_warehouse_id=warehouse.id,
            doc_type="writeoff",
            doc_id=1,
        )


async def test_yetkazish_rezervni_ham_qoldiqni_ham_kamaytiradi(session, base_data):
    warehouse = base_data["warehouse"]
    product = base_data["implant"]

    await stock_service.apply_move(
        session,
        kind=MoveKind.IN,
        product_id=product.id,
        qty=10,
        to_warehouse_id=warehouse.id,
        doc_type="receipt",
        doc_id=1,
    )
    await stock_service.reserve(session, warehouse.id, [MoveLine(product.id, 4)])
    await stock_service.ship(
        session,
        warehouse_id=warehouse.id,
        lines=[MoveLine(product.id, 4)],
        doc_type="order",
        doc_id=1,
    )

    row = await session.get(Stock, (warehouse.id, product.id))
    assert row.qty == 6
    assert row.reserved_qty == 0


async def test_kochirish_ikkala_omborni_ozgartiradi(session, base_data):
    main = base_data["warehouse"]
    product = base_data["implant"]

    agent_wh = Warehouse(name="Agent ombori", kind=WarehouseKind.AGENT, is_active=True)
    session.add(agent_wh)
    await session.flush()

    await stock_service.apply_move(
        session,
        kind=MoveKind.IN,
        product_id=product.id,
        qty=20,
        to_warehouse_id=main.id,
        doc_type="receipt",
        doc_id=1,
    )
    await stock_service.apply_move(
        session,
        kind=MoveKind.TRANSFER,
        product_id=product.id,
        qty=7,
        from_warehouse_id=main.id,
        to_warehouse_id=agent_wh.id,
        doc_type="transfer",
        doc_id=1,
    )

    assert await stock_service.get_qty(session, main.id, product.id) == 13
    assert await stock_service.get_qty(session, agent_wh.id, product.id) == 7


async def test_manfiy_miqdor_rad_etiladi(session, base_data):
    with pytest.raises(StockError):
        await stock_service.apply_move(
            session,
            kind=MoveKind.IN,
            product_id=base_data["implant"].id,
            qty=0,
            to_warehouse_id=base_data["warehouse"].id,
        )
