"""Ombor qoldig'i bilan ishlash.

Qoidalar:
  * Qoldiq faqat shu servis orqali o'zgaradi va har o'zgarish `stock_moves` ga yoziladi.
  * Qoldiq hech qachon manfiy bo'lmaydi.
  * Tasdiqlangan buyurtma tovarni band qiladi (`reserved_qty`), yetkazilganda
    haqiqiy qoldiqdan yechiladi.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import MoveKind, Product, Stock, StockMove, User, Warehouse, utcnow


class StockError(Exception):
    """Qoldiq yetarli emas yoki amal noto'g'ri."""


@dataclass(frozen=True)
class MoveLine:
    product_id: int
    qty: int


async def _locked_stock(
    session: AsyncSession, warehouse_id: int, product_id: int, create: bool = True
) -> Stock | None:
    stmt = select(Stock).where(
        Stock.warehouse_id == warehouse_id, Stock.product_id == product_id
    )
    if not settings.is_sqlite:
        stmt = stmt.with_for_update()
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None and create:
        row = Stock(warehouse_id=warehouse_id, product_id=product_id, qty=0, reserved_qty=0)
        session.add(row)
        await session.flush()
    return row


async def get_qty(session: AsyncSession, warehouse_id: int, product_id: int) -> int:
    row = await _locked_stock(session, warehouse_id, product_id, create=False)
    return row.qty if row else 0


async def get_available(session: AsyncSession, warehouse_id: int, product_id: int) -> int:
    row = await _locked_stock(session, warehouse_id, product_id, create=False)
    return (row.qty - row.reserved_qty) if row else 0


async def apply_move(
    session: AsyncSession,
    *,
    kind: MoveKind,
    product_id: int,
    qty: int,
    from_warehouse_id: int | None = None,
    to_warehouse_id: int | None = None,
    doc_type: str | None = None,
    doc_id: int | None = None,
    user: User | None = None,
    note: str | None = None,
    consume_reserved: bool = False,
) -> StockMove:
    """Bitta mahsulot bo'yicha qoldiqni o'zgartiradi va harakatni yozadi."""
    if qty <= 0:
        raise StockError("Miqdor 0 dan katta bo'lishi kerak")
    if from_warehouse_id is None and to_warehouse_id is None:
        raise StockError("Ombor ko'rsatilmagan")

    if from_warehouse_id is not None:
        src = await _locked_stock(session, from_warehouse_id, product_id)
        assert src is not None
        if src.qty < qty:
            product = await session.get(Product, product_id)
            name = product.name if product else f"#{product_id}"
            raise StockError(
                f"«{name}» omborda yetarli emas: mavjud {src.qty}, kerak {qty}"
            )
        src.qty -= qty
        if consume_reserved:
            src.reserved_qty = max(0, src.reserved_qty - qty)
        elif src.qty < src.reserved_qty:
            # Band qilingan tovarni boshqa hujjat bilan yechib yubormaslik uchun
            raise StockError(
                "Tovarning bu qismi boshqa buyurtma uchun band qilingan"
            )
        src.updated_at = utcnow()

    if to_warehouse_id is not None:
        dst = await _locked_stock(session, to_warehouse_id, product_id)
        assert dst is not None
        dst.qty += qty
        dst.updated_at = utcnow()

    move = StockMove(
        created_at=utcnow(),
        kind=kind,
        product_id=product_id,
        from_warehouse_id=from_warehouse_id,
        to_warehouse_id=to_warehouse_id,
        qty=qty,
        doc_type=doc_type,
        doc_id=doc_id,
        user_id=user.id if user else None,
        note=note,
    )
    session.add(move)
    await session.flush()
    return move


async def reserve(
    session: AsyncSession, warehouse_id: int, lines: list[MoveLine]
) -> None:
    """Buyurtma tasdiqlanganda tovarni band qiladi."""
    for line in sorted(lines, key=lambda x: x.product_id):
        row = await _locked_stock(session, warehouse_id, line.product_id)
        assert row is not None
        available = row.qty - row.reserved_qty
        if available < line.qty:
            product = await session.get(Product, line.product_id)
            name = product.name if product else f"#{line.product_id}"
            raise StockError(
                f"«{name}» yetarli emas: bo'sh {available} dona, kerak {line.qty} dona"
            )
        row.reserved_qty += line.qty
        row.updated_at = utcnow()
    await session.flush()


async def release_reserve(
    session: AsyncSession, warehouse_id: int, lines: list[MoveLine]
) -> None:
    """Buyurtma bekor qilinganda bandlikni bo'shatadi."""
    for line in sorted(lines, key=lambda x: x.product_id):
        row = await _locked_stock(session, warehouse_id, line.product_id, create=False)
        if row is None:
            continue
        row.reserved_qty = max(0, row.reserved_qty - line.qty)
        row.updated_at = utcnow()
    await session.flush()


async def ship(
    session: AsyncSession,
    *,
    warehouse_id: int,
    lines: list[MoveLine],
    doc_type: str,
    doc_id: int,
    user: User | None = None,
) -> None:
    """Yetkazilganda: bandlikni ham, haqiqiy qoldiqni ham kamaytiradi."""
    for line in sorted(lines, key=lambda x: x.product_id):
        await apply_move(
            session,
            kind=MoveKind.SALE,
            product_id=line.product_id,
            qty=line.qty,
            from_warehouse_id=warehouse_id,
            doc_type=doc_type,
            doc_id=doc_id,
            user=user,
            consume_reserved=True,
        )


async def ensure_agent_warehouse(session: AsyncSession, agent: User) -> Warehouse | None:
    """Agentda qo'l ombori yoqilgan bo'lsa — omborini yaratadi/qaytaradi."""
    if not agent.has_own_stock:
        return None
    wh = (
        await session.execute(select(Warehouse).where(Warehouse.owner_user_id == agent.id))
    ).scalar_one_or_none()
    if wh is None:
        from app.models import WarehouseKind

        wh = Warehouse(
            name=f"{agent.full_name} ombori",
            kind=WarehouseKind.AGENT,
            owner_user_id=agent.id,
            is_active=True,
        )
        session.add(wh)
        await session.flush()
    elif not wh.is_active:
        wh.is_active = True
        await session.flush()
    return wh


async def main_warehouse(session: AsyncSession) -> Warehouse:
    """Markaziy ombor (bo'lmasa yaratiladi)."""
    from app.models import WarehouseKind

    wh = (
        await session.execute(
            select(Warehouse)
            .where(Warehouse.kind == WarehouseKind.MAIN)
            .order_by(Warehouse.id)
            .limit(1)
        )
    ).scalar_one_or_none()
    if wh is None:
        wh = Warehouse(name="Markaziy ombor", kind=WarehouseKind.MAIN, is_active=True)
        session.add(wh)
        await session.flush()
    return wh
