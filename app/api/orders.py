"""Buyurtma oqimi API: yaratish, tasdiqlash, yig'ish, yetkazish, bekor qilish."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth import get_current_user, require_perm
from app.db import get_session
from app.models import (
    STATUS_LABELS_UZ,
    Doctor,
    Order,
    OrderSource,
    OrderStatus,
    Product,
    Role,
    User,
    Warehouse,
)
from app.permissions import (
    ORDERS_CREATE,
    agent_scope,
    user_can,
    ORDERS_DIRECTOR,
    ORDERS_FULFILL,
    ORDERS_VIEW,
    can,
)
from app.schemas import CancelIn, OkOut, OrderIn, OrderItemOut, OrderOut
from app.services import (
    contracts as contracts_service,
    notifications,
    orders as orders_service,
    stock as stock_service,
)
from app.services.fx import usd_to_uzs
from app.utils.audit import log_action
from app.utils.pdf import build_invoice_pdf

router = APIRouter(prefix="/orders", tags=["orders"])


async def _to_out(session: AsyncSession, order: Order) -> OrderOut:
    out = OrderOut.model_validate(order)
    out.status_label = STATUS_LABELS_UZ.get(order.status)
    out.debt_usd = order.debt_usd
    out.total_uzs = usd_to_uzs(order.total_usd, order.fx_rate)

    doctor = await session.get(Doctor, order.doctor_id)
    if doctor:
        out.doctor_name = doctor.full_name
        out.doctor_phone = doctor.phone
    if order.agent_id:
        agent = await session.get(User, order.agent_id)
        out.agent_name = agent.full_name if agent else None
    warehouse = await session.get(Warehouse, order.warehouse_id)
    out.warehouse_name = warehouse.name if warehouse else None

    if order.contract_id:
        from app.models import Contract

        contract = await session.get(Contract, order.contract_id)
        if contract is not None:
            out.contract_number = contract.number
            out.contract_tariff = contract.tariff_name

    items = []
    for item in order.items:
        product = await session.get(Product, item.product_id)
        item_out = OrderItemOut.model_validate(item)
        if product:
            item_out.product_name = product.name
            item_out.sku = product.sku
            item_out.size = product.size_label
        items.append(item_out)
    out.items = items
    return out


async def _load(session: AsyncSession, order_id: int) -> Order:
    order = (
        await session.execute(
            select(Order).options(selectinload(Order.items)).where(Order.id == order_id)
        )
    ).scalar_one_or_none()
    if order is None:
        raise HTTPException(404, "Buyurtma topilmadi")
    return order


async def _check_access(session: AsyncSession, order: Order, user: User) -> None:
    scope = agent_scope(user)
    if scope is not None and order.agent_id != scope:
        raise HTTPException(403, "Bu buyurtma sizga tegishli emas")
    if user.role is Role.DOCTOR:
        doctor = await session.get(Doctor, order.doctor_id)
        if doctor is None or doctor.user_id != user.id:
            raise HTTPException(403, "Bu buyurtma sizga tegishli emas")


@router.get("", response_model=list[OrderOut])
async def list_orders(
    status: OrderStatus | None = None,
    doctor_id: int | None = None,
    agent_id: int | None = None,
    only_open: bool = False,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_perm(ORDERS_VIEW)),
):
    stmt = select(Order).options(selectinload(Order.items))

    scope = agent_scope(user)
    if scope is not None:
        stmt = stmt.where(Order.agent_id == scope)
    elif user.role is Role.DOCTOR:
        doctor_row = (
            await session.execute(select(Doctor.id).where(Doctor.user_id == user.id))
        ).scalar_one_or_none()
        stmt = stmt.where(Order.doctor_id == (doctor_row or 0))
    elif user_can(user, ORDERS_FULFILL) and only_open:
        stmt = stmt.where(
            Order.status.in_([OrderStatus.APPROVED, OrderStatus.PICKING, OrderStatus.SHIPPED])
        )

    if status is not None:
        stmt = stmt.where(Order.status == status)
    if doctor_id is not None:
        stmt = stmt.where(Order.doctor_id == doctor_id)
    if agent_id is not None and user.role not in (Role.AGENT, Role.DOCTOR):
        stmt = stmt.where(Order.agent_id == agent_id)
    if only_open and not user_can(user, ORDERS_FULFILL):
        from app.models import OPEN_STATUSES

        stmt = stmt.where(Order.status.in_(list(OPEN_STATUSES)))

    rows = (
        await session.execute(stmt.order_by(Order.id.desc()).limit(limit).offset(offset))
    ).scalars().all()
    return [await _to_out(session, order) for order in rows]


@router.get("/{order_id}", response_model=OrderOut)
async def get_order(
    order_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_perm(ORDERS_VIEW)),
):
    order = await _load(session, order_id)
    await _check_access(session, order, user)
    return await _to_out(session, order)


@router.post("", response_model=OrderOut, status_code=201)
async def create_order(
    payload: OrderIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_perm(ORDERS_CREATE)),
):
    if user.role is Role.DOCTOR:
        doctor = (
            await session.execute(select(Doctor).where(Doctor.user_id == user.id))
        ).scalar_one_or_none()
        if doctor is None:
            raise HTTPException(404, "Vrach kartochkangiz topilmadi")
        source = OrderSource.DOCTOR
    else:
        if payload.doctor_id is None:
            raise HTTPException(400, "Vrachni tanlang")
        doctor = await session.get(Doctor, payload.doctor_id)
        if doctor is None or not doctor.is_active:
            raise HTTPException(404, "Vrach topilmadi")
        if agent_scope(user) is not None and doctor.agent_id not in (None, user.id):
            raise HTTPException(403, "Bu vrach sizga biriktirilmagan")
        source = OrderSource.AGENT

    try:
        order = await orders_service.create_order(
            session,
            doctor=doctor,
            lines=[
                orders_service.LineInput(line.product_id, line.qty, line.discount_pct)
                for line in payload.lines
            ],
            actor=user,
            source=source,
            warehouse_id=payload.warehouse_id,
            discount_pct=payload.discount_pct,
            comment=payload.comment,
        )
    except orders_service.OrderError as exc:
        raise HTTPException(400, str(exc)) from exc

    # Vrachda ochiq taklif-shartnoma bo'lsa buyurtma o'ziga bog'lanadi.
    # Bir vaqtda bitta shartnoma ochiq bo'lgani uchun tanlash oynasi
    # kerak emas — agent hech narsani eslab qolishi shart emas.
    shartnoma = await contracts_service.open_contract(session, doctor.id)
    if shartnoma is not None:
        order.contract_id = shartnoma.id
        await session.flush()

    await log_action(
        session, user, "create", "order", order.id,
        new={
            "number": order.number,
            "total_usd": str(order.total_usd),
            "shartnoma": shartnoma.number if shartnoma else None,
        },
    )
    await notifications.order_created(session, order)
    if order.needs_director:
        await notifications.order_needs_director(session, order)

    return await _to_out(session, order)


@router.post("/{order_id}/approve", response_model=OrderOut)
async def approve_order(
    order_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_perm(ORDERS_VIEW)),
):
    """Agent yoki direktor tasdiqlaydi. Kerak bo'lsa direktorga uzatiladi."""
    order = await _load(session, order_id)
    await _check_access(session, order, user)

    if user.role is Role.DOCTOR:
        raise HTTPException(403, "Vrach buyurtmani tasdiqlay olmaydi")
    if order.status is OrderStatus.DIRECTOR_REVIEW and not user_can(user, ORDERS_DIRECTOR):
        raise HTTPException(403, "Buni faqat direktor tasdiqlaydi")

    previous = order.status
    try:
        order = await orders_service.approve(session, order, user)
    except (orders_service.OrderError, stock_service.StockError) as exc:
        raise HTTPException(400, str(exc)) from exc

    details: dict = {"status": order.status.value}
    # Bitta xodim ham agent, ham direktor bo'lsa — o'zi yozgan chegirmali
    # buyurtmani o'zi tasdiqlashi mumkin. Buni bekor qilmaymiz (aks holda
    # direktor bitta bo'lsa buyurtma osilib qoladi), lekin audit jurnalida
    # ko'rinib turadi — ta'sischi va super-admin nazorat qila oladi.
    if (
        order.status is OrderStatus.APPROVED
        and order.needs_director
        and order.agent_id == user.id
    ):
        details["ozini_ozi_tasdiqladi"] = True

    await log_action(
        session, user, "approve", "order", order.id,
        old={"status": previous.value}, new=details,
    )
    if order.status is OrderStatus.DIRECTOR_REVIEW:
        await notifications.order_needs_director(session, order)
    elif order.status is OrderStatus.APPROVED:
        await notifications.order_approved(session, order)

    return await _to_out(session, order)


@router.post("/{order_id}/picking", response_model=OrderOut)
async def start_picking(
    order_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_perm(ORDERS_FULFILL)),
):
    order = await _load(session, order_id)
    try:
        order = await orders_service.start_picking(session, order, user)
    except orders_service.OrderError as exc:
        raise HTTPException(400, str(exc)) from exc
    await log_action(session, user, "picking", "order", order.id)
    return await _to_out(session, order)


@router.post("/{order_id}/ship", response_model=OrderOut)
async def ship_order(
    order_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_perm(ORDERS_FULFILL)),
):
    order = await _load(session, order_id)
    try:
        order = await orders_service.ship(session, order, user)
    except orders_service.OrderError as exc:
        raise HTTPException(400, str(exc)) from exc
    await log_action(session, user, "ship", "order", order.id)
    return await _to_out(session, order)


@router.post("/{order_id}/deliver", response_model=OrderOut)
async def deliver_order(
    order_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_perm(ORDERS_FULFILL)),
):
    """Yetkazildi — tovar qoldiqdan yechiladi, qarz va to'lov muddati paydo bo'ladi."""
    order = await _load(session, order_id)
    try:
        order = await orders_service.deliver(session, order, user)
    except (orders_service.OrderError, stock_service.StockError) as exc:
        raise HTTPException(400, str(exc)) from exc

    await log_action(
        session, user, "deliver", "order", order.id,
        new={"total_usd": str(order.total_usd), "due_date": str(order.due_date)},
    )
    await notifications.order_delivered(session, order)
    await notifications.check_low_stock(
        session, [item.product_id for item in order.items]
    )
    return await _to_out(session, order)


@router.post("/{order_id}/cancel", response_model=OrderOut)
async def cancel_order(
    order_id: int,
    payload: CancelIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_perm(ORDERS_VIEW)),
):
    order = await _load(session, order_id)
    await _check_access(session, order, user)

    if user.role is Role.DOCTOR and order.status is not OrderStatus.NEW:
        raise HTTPException(400, "Tasdiqlangan buyurtmani agentingiz bekor qiladi")

    try:
        order = await orders_service.cancel(session, order, user, payload.reason)
    except orders_service.OrderError as exc:
        raise HTTPException(400, str(exc)) from exc

    await log_action(
        session, user, "cancel", "order", order.id, comment=payload.reason
    )
    await notifications.order_cancelled(session, order)
    return await _to_out(session, order)


@router.get("/{order_id}/invoice.pdf")
async def order_invoice(
    order_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_perm(ORDERS_VIEW)),
):
    """Vrachga beriladigan hisob-faktura (PDF)."""
    order = await _load(session, order_id)
    await _check_access(session, order, user)
    out = await _to_out(session, order)
    stream = await build_invoice_pdf(session, out)
    return StreamingResponse(
        stream,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{order.number}.pdf"'
        },
    )
