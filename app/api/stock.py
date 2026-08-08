"""Ombor: qoldiq, kirim, ko'chirish, korreksiya, spisaniye, harakat jurnali."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user, require_perm
from app.db import get_session
from app.models import Role, User, Warehouse
from app.permissions import STOCK_EDIT, STOCK_VIEW
from app.schemas import (
    AdjustIn,
    OkOut,
    ReceiptIn,
    StockRowOut,
    TransferIn,
    WarehouseOut,
    WriteOffIn,
)
from app.services import inventory_ops, orders as orders_service, reports, stock as stock_service
from app.utils.audit import log_action

router = APIRouter(prefix="/stock", tags=["stock"])


async def _accessible_warehouse(
    session: AsyncSession, user: User, warehouse_id: int | None
) -> Warehouse:
    """Agent faqat o'z omborida ish yuritadi, ombor xodimi/rahbariyat — hammasida."""
    if user.role is Role.AGENT:
        own = await stock_service.ensure_agent_warehouse(session, user)
        if own is None:
            raise HTTPException(403, "Sizda qo'l ombori yoqilmagan")
        if warehouse_id is not None and warehouse_id != own.id:
            raise HTTPException(403, "Faqat o'z omboringiz bilan ishlay olasiz")
        return own

    if warehouse_id is None:
        return await stock_service.main_warehouse(session)
    warehouse = await session.get(Warehouse, warehouse_id)
    if warehouse is None or not warehouse.is_active:
        raise HTTPException(404, "Ombor topilmadi")
    return warehouse


@router.get("/warehouses", response_model=list[WarehouseOut])
async def list_warehouses(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_perm(STOCK_VIEW)),
):
    stmt = select(Warehouse).where(Warehouse.is_active.is_(True)).order_by(
        Warehouse.kind, Warehouse.name
    )
    if user.role is Role.AGENT:
        main = await stock_service.main_warehouse(session)
        stmt = stmt.where(
            (Warehouse.owner_user_id == user.id) | (Warehouse.id == main.id)
        )
    return (await session.execute(stmt)).scalars().all()


@router.get("/balances", response_model=list[StockRowOut])
async def balances(
    warehouse_id: int | None = None,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_perm(STOCK_VIEW)),
):
    return await reports.stock_by_product(session, warehouse_id)


@router.get("/by-warehouse")
async def by_warehouse(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_perm(STOCK_VIEW)),
):
    return await reports.stock_by_warehouse(session)


@router.get("/low")
async def low_stock(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_perm(STOCK_VIEW)),
):
    """Omborda kam qolgan mahsulotlar va necha kunga yetishi."""
    return await reports.low_stock(session)


@router.get("/moves")
async def moves(
    warehouse_id: int | None = None,
    product_id: int | None = None,
    limit: int = Query(default=100, le=500),
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_perm(STOCK_VIEW)),
):
    return await reports.stock_moves_journal(
        session, limit=limit, warehouse_id=warehouse_id, product_id=product_id
    )


@router.post("/receipts", response_model=OkOut, status_code=201)
async def create_receipt(
    payload: ReceiptIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_perm(STOCK_EDIT)),
):
    """Yetkazib beruvchidan kirim."""
    warehouse = await _accessible_warehouse(session, user, payload.warehouse_id)
    try:
        receipt = await orders_service.receive_stock(
            session,
            warehouse_id=warehouse.id,
            lines=[(line.product_id, line.qty, line.cost_usd) for line in payload.lines],
            actor=user,
            supplier=payload.supplier,
            invoice_no=payload.invoice_no,
            note=payload.note,
        )
    except (orders_service.OrderError, stock_service.StockError) as exc:
        raise HTTPException(400, str(exc)) from exc

    await log_action(
        session, user, "receipt", "stock", receipt.id,
        new={"number": receipt.number, "warehouse_id": warehouse.id, "lines": len(payload.lines)},
    )
    return OkOut(ok=True, message=f"Kirim rasmiylashtirildi: {receipt.number}")


@router.post("/transfers", response_model=OkOut, status_code=201)
async def create_transfer(
    payload: TransferIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_perm(STOCK_EDIT)),
):
    """Omborlar orasida ko'chirish (markaziy ombordan agentga)."""
    if user.role is Role.AGENT:
        own = await stock_service.ensure_agent_warehouse(session, user)
        if own is None or payload.from_warehouse_id != own.id:
            raise HTTPException(403, "Agent faqat o'z omboridan ko'chira oladi")

    try:
        doc = await orders_service.transfer_stock(
            session,
            from_warehouse_id=payload.from_warehouse_id,
            to_warehouse_id=payload.to_warehouse_id,
            lines=[(line.product_id, line.qty) for line in payload.lines],
            actor=user,
            note=payload.note,
        )
    except (orders_service.OrderError, stock_service.StockError) as exc:
        raise HTTPException(400, str(exc)) from exc

    await log_action(
        session, user, "transfer", "stock", doc.id,
        new={
            "number": doc.number,
            "from": payload.from_warehouse_id,
            "to": payload.to_warehouse_id,
        },
    )
    return OkOut(ok=True, message=f"Ko'chirish bajarildi: {doc.number}")


@router.post("/adjust", response_model=OkOut)
async def adjust(
    payload: AdjustIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_perm(STOCK_EDIT)),
):
    """Inventarizatsiya — qoldiqni haqiqiy songa keltirish."""
    warehouse = await _accessible_warehouse(session, user, payload.warehouse_id)
    before = await stock_service.get_qty(session, warehouse.id, payload.product_id)
    try:
        delta = await inventory_ops.adjust_stock(
            session,
            warehouse_id=warehouse.id,
            product_id=payload.product_id,
            new_qty=payload.new_qty,
            actor=user,
            note=payload.note,
        )
    except (inventory_ops.InventoryOpError, stock_service.StockError) as exc:
        raise HTTPException(400, str(exc)) from exc

    await log_action(
        session, user, "adjust", "stock", payload.product_id,
        old={"qty": before}, new={"qty": payload.new_qty}, comment=payload.note,
    )
    if delta == 0:
        return OkOut(ok=True, message="Qoldiq allaqachon to'g'ri edi")
    sign = "+" if delta > 0 else ""
    return OkOut(ok=True, message=f"Qoldiq to'g'rilandi ({sign}{delta})")


@router.post("/writeoffs", response_model=OkOut, status_code=201)
async def create_writeoff(
    payload: WriteOffIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_perm(STOCK_EDIT)),
):
    """Spisaniye — yaroqsiz yoki yo'qolgan tovarni hisobdan chiqarish."""
    warehouse = await _accessible_warehouse(session, user, payload.warehouse_id)
    try:
        doc = await inventory_ops.create_writeoff(
            session,
            warehouse_id=warehouse.id,
            lines=[(line.product_id, line.qty) for line in payload.lines],
            actor=user,
            reason=payload.reason,
        )
    except (inventory_ops.InventoryOpError, stock_service.StockError) as exc:
        raise HTTPException(400, str(exc)) from exc

    await log_action(
        session, user, "writeoff", "stock", doc.id,
        new={"number": doc.number, "total_usd": str(doc.total_usd), "reason": payload.reason},
    )
    return OkOut(ok=True, message=f"Spisaniye rasmiylashtirildi: {doc.number}")
