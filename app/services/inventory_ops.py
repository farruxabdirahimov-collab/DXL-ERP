"""Qaytarish (vozvrat) va spisaniye hujjatlari."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Contract,
    Doctor,
    MoveKind,
    Order,
    OrderItem,
    Product,
    Return,
    ReturnItem,
    User,
    WriteOff,
    WriteOffItem,
    utcnow,
)
from app.services import stock as stock_service
from app.services.fx import round_money
from app.services.numbering import next_number

ZERO = Decimal("0.00")


class InventoryOpError(Exception):
    pass


async def create_return(
    session: AsyncSession,
    *,
    doctor: Doctor,
    warehouse_id: int,
    lines: list[tuple[int, int]],
    actor: User,
    order_id: int | None = None,
    reason: str | None = None,
) -> Return:
    """Vrachdan tovar qaytarish: ombor qoldig'i oshadi, qarzi kamayadi."""
    if not lines:
        raise InventoryOpError("Qaytarish bo'sh")

    merged: dict[int, int] = {}
    for product_id, qty in lines:
        if qty <= 0:
            raise InventoryOpError("Miqdor 0 dan katta bo'lishi kerak")
        merged[product_id] = merged.get(product_id, 0) + qty

    order: Order | None = None
    sold_prices: dict[int, Decimal] = {}
    if order_id:
        order = await session.get(Order, order_id)
        if order is None or order.doctor_id != doctor.id:
            raise InventoryOpError("Buyurtma topilmadi yoki bu vrachga tegishli emas")
        sold_qty: dict[int, int] = {}
        for item in order.items:
            sold_prices[item.product_id] = Decimal(item.line_total_usd) / Decimal(item.qty)
            sold_qty[item.product_id] = item.qty
        for product_id, qty in merged.items():
            if product_id not in sold_qty:
                raise InventoryOpError("Bu mahsulot ushbu buyurtmada yo'q")
            if qty > sold_qty[product_id]:
                raise InventoryOpError(
                    f"Qaytarish miqdori sotilganidan ko'p (#{product_id})"
                )

    # Qaytarish qaysi agent hisobidan ayirilishini aniqlaymiz:
    # buyurtma bo'lsa — o'shaning agenti, aks holda vrachning agenti
    agent_id = order.agent_id if order is not None else doctor.agent_id

    doc = Return(
        number=await next_number(session, "return"),
        doctor_id=doctor.id,
        order_id=order_id,
        warehouse_id=warehouse_id,
        agent_id=agent_id,
        reason=reason,
        created_by_id=actor.id,
    )
    session.add(doc)
    await session.flush()

    total = ZERO
    for product_id, qty in sorted(merged.items()):
        product = await session.get(Product, product_id)
        if product is None:
            raise InventoryOpError(f"Mahsulot topilmadi (#{product_id})")
        unit_price = sold_prices.get(product_id, Decimal(product.price_usd))
        line_total = round_money(unit_price * qty)
        session.add(
            ReturnItem(
                return_id=doc.id,
                product_id=product_id,
                qty=qty,
                price_usd=round_money(unit_price),
                line_total_usd=line_total,
            )
        )
        total += line_total
        await stock_service.apply_move(
            session,
            kind=MoveKind.RETURN,
            product_id=product_id,
            qty=qty,
            to_warehouse_id=warehouse_id,
            doc_type="return",
            doc_id=doc.id,
            user=actor,
        )

    doc.total_usd = round_money(total)

    if order is not None:
        order.returned_usd = round_money(Decimal(order.returned_usd) + doc.total_usd)
        if order.paid_usd + order.returned_usd >= order.total_usd:
            order.closed_at = utcnow()

    # Vrachning umumiy xaridi ham kamayadi — aks holda toifasi shishib qoladi
    doctor.total_purchased_usd = round_money(
        max(Decimal("0"), Decimal(doctor.total_purchased_usd) - doc.total_usd)
    )

    # Shartnoma bo'yicha tovar qaytarilsa — sovg'a bekor bo'ladi (kelishilgan
    # qoida). Qarz odatdagidek kamayadi, paket narxi o'zgarmaydi.
    from app.services import contracts as contracts_service

    shartnoma = None
    if order is not None and order.contract_id:
        shartnoma = await session.get(Contract, order.contract_id)
    if shartnoma is None:
        shartnoma = await contracts_service.open_contract(session, doctor.id)
    if shartnoma is not None:
        await contracts_service.register_return(session, shartnoma, doc.total_usd)

    await session.flush()
    return doc


async def create_writeoff(
    session: AsyncSession,
    *,
    warehouse_id: int,
    lines: list[tuple[int, int]],
    actor: User,
    reason: str,
) -> WriteOff:
    """Spisaniye — yaroqsiz/singan/yo'qolgan tovarni hisobdan chiqarish."""
    if not lines:
        raise InventoryOpError("Spisaniye bo'sh")
    if not reason or not reason.strip():
        raise InventoryOpError("Spisaniye sababini ko'rsating")

    merged: dict[int, int] = {}
    for product_id, qty in lines:
        if qty <= 0:
            raise InventoryOpError("Miqdor 0 dan katta bo'lishi kerak")
        merged[product_id] = merged.get(product_id, 0) + qty

    doc = WriteOff(
        number=await next_number(session, "writeoff"),
        warehouse_id=warehouse_id,
        reason=reason.strip(),
        created_by_id=actor.id,
    )
    session.add(doc)
    await session.flush()

    total = ZERO
    for product_id, qty in sorted(merged.items()):
        product = await session.get(Product, product_id)
        if product is None:
            raise InventoryOpError(f"Mahsulot topilmadi (#{product_id})")
        price = Decimal(product.price_usd)
        session.add(
            WriteOffItem(
                writeoff_id=doc.id, product_id=product_id, qty=qty, price_usd=price
            )
        )
        total += round_money(price * qty)
        await stock_service.apply_move(
            session,
            kind=MoveKind.WRITEOFF,
            product_id=product_id,
            qty=qty,
            from_warehouse_id=warehouse_id,
            doc_type="writeoff",
            doc_id=doc.id,
            user=actor,
            note=reason,
        )

    doc.total_usd = round_money(total)
    await session.flush()
    return doc


async def adjust_stock(
    session: AsyncSession,
    *,
    warehouse_id: int,
    product_id: int,
    new_qty: int,
    actor: User,
    note: str | None = None,
) -> int:
    """Inventarizatsiya: qoldiqni haqiqiy songa keltirish. Farqni qaytaradi."""
    if new_qty < 0:
        raise InventoryOpError("Qoldiq manfiy bo'lishi mumkin emas")
    current = await stock_service.get_qty(session, warehouse_id, product_id)
    delta = new_qty - current
    if delta == 0:
        return 0

    if delta > 0:
        await stock_service.apply_move(
            session,
            kind=MoveKind.ADJUST,
            product_id=product_id,
            qty=delta,
            to_warehouse_id=warehouse_id,
            doc_type="adjust",
            user=actor,
            note=note or "Inventarizatsiya",
        )
    else:
        await stock_service.apply_move(
            session,
            kind=MoveKind.ADJUST,
            product_id=product_id,
            qty=-delta,
            from_warehouse_id=warehouse_id,
            doc_type="adjust",
            user=actor,
            note=note or "Inventarizatsiya",
        )
    return delta
