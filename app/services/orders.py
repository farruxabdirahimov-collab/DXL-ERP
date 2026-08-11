"""Buyurtma oqimi: yaratish -> tasdiqlash -> yig'ish -> yetkazish.

Oqim (foydalanuvchi tanlovi bo'yicha):
    Vrach buyurtma beradi -> AGENT tasdiqlaydi -> (kerak bo'lsa DIREKTOR) -> OMBOR
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Doctor,
    MoveKind,
    Order,
    OrderItem,
    OrderSource,
    OrderStatus,
    Product,
    Role,
    User,
    Warehouse,
    utcnow,
)
from app.permissions import ORDERS_DIRECTOR, user_can
from app.services import stock as stock_service
from app.services.debt import compute_due_date, credit_check
from app.services.fx import get_rate, round_money, today_local
from app.services.numbering import next_number
from app.services.settings_service import get_setting
from app.services.stock import MoveLine

ZERO = Decimal("0.00")


class OrderError(Exception):
    """Buyurtma oqimidagi qoidabuzarlik."""


@dataclass
class LineInput:
    product_id: int
    qty: int
    discount_pct: Decimal = ZERO


def _line_total(qty: int, price: Decimal, discount_pct: Decimal) -> Decimal:
    gross = Decimal(qty) * Decimal(price)
    return round_money(gross * (Decimal("100") - Decimal(discount_pct)) / Decimal("100"))


def recalc_totals(order: Order, items: list[OrderItem]) -> None:
    subtotal = sum((item.line_total_usd for item in items), ZERO)
    order.subtotal_usd = round_money(subtotal)
    order.discount_usd = round_money(
        order.subtotal_usd * Decimal(order.discount_pct) / Decimal("100")
    )
    order.total_usd = round_money(order.subtotal_usd - order.discount_usd)


def effective_discount_pct(order: Order, items: list[OrderItem], list_total: Decimal) -> Decimal:
    """Prays-listga nisbatan haqiqiy chegirma foizi."""
    if list_total <= 0:
        return ZERO
    return round_money(
        (list_total - order.total_usd) / list_total * Decimal("100")
    )


async def _resolve_warehouse(
    session: AsyncSession, actor: User, doctor: Doctor, warehouse_id: int | None
) -> Warehouse:
    if warehouse_id is not None:
        wh = await session.get(Warehouse, warehouse_id)
        if wh is None or not wh.is_active:
            raise OrderError("Ombor topilmadi")
        return wh

    # Agent o'z qo'l omboridan sotadi (yoqilgan bo'lsa)
    agent_id = actor.id if actor.role is Role.AGENT else doctor.agent_id
    if agent_id:
        agent = await session.get(User, agent_id)
        if agent and agent.has_own_stock:
            wh = await stock_service.ensure_agent_warehouse(session, agent)
            if wh is not None:
                return wh
    return await stock_service.main_warehouse(session)


async def create_order(
    session: AsyncSession,
    *,
    doctor: Doctor,
    lines: list[LineInput],
    actor: User,
    source: OrderSource,
    warehouse_id: int | None = None,
    discount_pct: Decimal = ZERO,
    comment: str | None = None,
) -> Order:
    if not lines:
        raise OrderError("Buyurtma bo'sh — kamida bitta mahsulot qo'shing")

    merged: dict[int, LineInput] = {}
    for line in lines:
        if line.qty <= 0:
            raise OrderError("Miqdor 0 dan katta bo'lishi kerak")
        if line.product_id in merged:
            prev = merged[line.product_id]
            merged[line.product_id] = LineInput(
                prev.product_id, prev.qty + line.qty, max(prev.discount_pct, line.discount_pct)
            )
        else:
            merged[line.product_id] = line

    warehouse = await _resolve_warehouse(session, actor, doctor, warehouse_id)
    rate = await get_rate(session)

    order = Order(
        number=await next_number(session, "order"),
        doctor_id=doctor.id,
        agent_id=doctor.agent_id or (actor.id if actor.role is Role.AGENT else None),
        warehouse_id=warehouse.id,
        source=source,
        status=OrderStatus.NEW,
        discount_pct=Decimal(discount_pct),
        fx_rate=rate,
        comment=comment,
        created_by_id=actor.id,
    )
    session.add(order)
    await session.flush()

    items: list[OrderItem] = []
    list_total = ZERO
    for line in merged.values():
        product = await session.get(Product, line.product_id)
        if product is None or not product.is_active:
            raise OrderError(f"Mahsulot topilmadi yoki faol emas (#{line.product_id})")
        price = Decimal(product.price_usd)
        line_discount = Decimal(line.discount_pct or 0)
        if doctor.discount_pct and line_discount < Decimal(doctor.discount_pct):
            line_discount = Decimal(doctor.discount_pct)
        item = OrderItem(
            order_id=order.id,
            product_id=product.id,
            qty=line.qty,
            price_usd=price,
            discount_pct=line_discount,
            line_total_usd=_line_total(line.qty, price, line_discount),
        )
        session.add(item)
        items.append(item)
        list_total += Decimal(line.qty) * price

    recalc_totals(order, items)

    # Chegirma va qarz nazorati
    max_discount = Decimal(str(await get_setting(session, "max_discount_pct_agent")))
    effective = effective_discount_pct(order, items, round_money(list_total))
    reasons: list[str] = []
    if effective > max_discount:
        reasons.append(f"Chegirma {effective}% (ruxsat {max_discount}%)")
    credit_reason = await credit_check(session, doctor, order.total_usd)
    if credit_reason:
        reasons.append(credit_reason)

    order.needs_director = bool(reasons)
    order.director_reason = "; ".join(reasons) if reasons else None

    await session.flush()
    await session.refresh(order)
    return order


async def _order_lines(order: Order) -> list[MoveLine]:
    return [MoveLine(product_id=i.product_id, qty=i.qty) for i in order.items]


async def approve(session: AsyncSession, order: Order, actor: User) -> Order:
    """Agent yoki direktor tasdiqlashi. Tovar band qilinadi."""
    if order.status not in (OrderStatus.NEW, OrderStatus.DIRECTOR_REVIEW):
        raise OrderError(f"Bu holatda tasdiqlab bo'lmaydi: {order.status.value}")

    # Ruxsat bo'yicha tekshiramiz, asosiy rol bo'yicha emas: bitta xodimda
    # bir necha vazifa bo'lsa (agent + direktor), direktorlik huquqini
    # qo'shimcha roldan oladi va buyurtma osilib qolmaydi.
    is_director = user_can(actor, ORDERS_DIRECTOR)

    if order.status is OrderStatus.NEW:
        if order.needs_director and not is_director:
            order.status = OrderStatus.DIRECTOR_REVIEW
            await session.flush()
            return order
    elif not is_director:
        raise OrderError("Bu buyurtmani faqat direktor tasdiqlay oladi")

    await stock_service.reserve(session, order.warehouse_id, await _order_lines(order))
    order.status = OrderStatus.APPROVED
    order.approved_by_id = actor.id
    order.approved_at = utcnow()
    await session.flush()
    return order


async def start_picking(session: AsyncSession, order: Order, actor: User) -> Order:
    if order.status is not OrderStatus.APPROVED:
        raise OrderError("Faqat tasdiqlangan buyurtmani yig'ish mumkin")
    order.status = OrderStatus.PICKING
    await session.flush()
    return order


async def ship(session: AsyncSession, order: Order, actor: User) -> Order:
    if order.status not in (OrderStatus.APPROVED, OrderStatus.PICKING):
        raise OrderError("Bu holatda jo'natib bo'lmaydi")
    order.status = OrderStatus.SHIPPED
    order.shipped_at = utcnow()
    await session.flush()
    return order


async def deliver(session: AsyncSession, order: Order, actor: User) -> Order:
    """Yetkazildi — qoldiqdan yechiladi, qarz va muddat paydo bo'ladi."""
    if order.status not in (OrderStatus.APPROVED, OrderStatus.PICKING, OrderStatus.SHIPPED):
        raise OrderError("Bu holatda yetkazilgan deb belgilab bo'lmaydi")

    await stock_service.ship(
        session,
        warehouse_id=order.warehouse_id,
        lines=await _order_lines(order),
        doc_type="order",
        doc_id=order.id,
        user=actor,
    )

    doctor = await session.get(Doctor, order.doctor_id)
    assert doctor is not None

    order.status = OrderStatus.DELIVERED
    order.delivered_at = utcnow()
    order.due_date = compute_due_date(today_local(), doctor)

    doctor.last_order_at = order.delivered_at
    doctor.total_purchased_usd = round_money(
        Decimal(doctor.total_purchased_usd) + order.total_usd
    )
    await session.flush()
    return order


async def cancel(
    session: AsyncSession, order: Order, actor: User, reason: str | None = None
) -> Order:
    if order.status is OrderStatus.DELIVERED:
        raise OrderError("Yetkazilgan buyurtmani bekor qilib bo'lmaydi — qaytarish rasmiylashtiring")
    if order.status in (OrderStatus.CANCELLED, OrderStatus.REJECTED):
        return order

    from app.models import RESERVED_STATUSES

    if order.status in RESERVED_STATUSES:
        await stock_service.release_reserve(
            session, order.warehouse_id, await _order_lines(order)
        )

    order.status = (
        OrderStatus.REJECTED
        if actor.role in (Role.DIRECTOR, Role.SUPERADMIN, Role.AGENT)
        and order.status in (OrderStatus.NEW, OrderStatus.DIRECTOR_REVIEW)
        else OrderStatus.CANCELLED
    )
    order.cancel_reason = reason
    order.closed_at = utcnow()
    await session.flush()
    return order


async def visible_orders_stmt(user: User):
    """Rolga qarab ko'rinadigan buyurtmalar."""
    stmt = select(Order)
    if user.role is Role.AGENT:
        stmt = stmt.where(Order.agent_id == user.id)
    elif user.role is Role.DOCTOR:
        stmt = stmt.join(Doctor, Doctor.id == Order.doctor_id).where(
            Doctor.user_id == user.id
        )
    return stmt


async def receive_stock(
    session: AsyncSession,
    *,
    warehouse_id: int,
    lines: list[tuple[int, int, Decimal]],
    actor: User,
    supplier: str | None = None,
    invoice_no: str | None = None,
    note: str | None = None,
):
    """Yetkazib beruvchidan kirim hujjati."""
    from app.models import Receipt, ReceiptItem

    if not lines:
        raise OrderError("Kirim bo'sh")

    merged: dict[int, tuple[int, Decimal]] = {}
    for product_id, qty, cost in lines:
        if qty <= 0:
            raise OrderError("Miqdor 0 dan katta bo'lishi kerak")
        prev_qty, prev_cost = merged.get(product_id, (0, cost))
        merged[product_id] = (prev_qty + qty, cost or prev_cost)

    receipt = Receipt(
        number=await next_number(session, "receipt"),
        warehouse_id=warehouse_id,
        supplier=supplier,
        invoice_no=invoice_no,
        note=note,
        created_by_id=actor.id,
    )
    session.add(receipt)
    await session.flush()

    total = ZERO
    for product_id, (qty, cost) in merged.items():
        session.add(
            ReceiptItem(
                receipt_id=receipt.id, product_id=product_id, qty=qty, cost_usd=cost or ZERO
            )
        )
        total += Decimal(qty) * Decimal(cost or 0)
        await stock_service.apply_move(
            session,
            kind=MoveKind.IN,
            product_id=product_id,
            qty=qty,
            to_warehouse_id=warehouse_id,
            doc_type="receipt",
            doc_id=receipt.id,
            user=actor,
        )

    receipt.total_usd = round_money(total)
    await session.flush()
    return receipt


async def transfer_stock(
    session: AsyncSession,
    *,
    from_warehouse_id: int,
    to_warehouse_id: int,
    lines: list[tuple[int, int]],
    actor: User,
    note: str | None = None,
):
    """Omborlar orasida ko'chirish (markaziy -> agent)."""
    from app.models import Transfer, TransferItem

    if from_warehouse_id == to_warehouse_id:
        raise OrderError("Bir xil omborga ko'chirib bo'lmaydi")
    if not lines:
        raise OrderError("Ko'chirish bo'sh")

    merged: dict[int, int] = {}
    for product_id, qty in lines:
        if qty <= 0:
            raise OrderError("Miqdor 0 dan katta bo'lishi kerak")
        merged[product_id] = merged.get(product_id, 0) + qty

    doc = Transfer(
        number=await next_number(session, "transfer"),
        from_warehouse_id=from_warehouse_id,
        to_warehouse_id=to_warehouse_id,
        note=note,
        created_by_id=actor.id,
    )
    session.add(doc)
    await session.flush()

    for product_id, qty in sorted(merged.items()):
        session.add(TransferItem(transfer_id=doc.id, product_id=product_id, qty=qty))
        await stock_service.apply_move(
            session,
            kind=MoveKind.TRANSFER,
            product_id=product_id,
            qty=qty,
            from_warehouse_id=from_warehouse_id,
            to_warehouse_id=to_warehouse_id,
            doc_type="transfer",
            doc_id=doc.id,
            user=actor,
        )

    await session.flush()
    return doc
