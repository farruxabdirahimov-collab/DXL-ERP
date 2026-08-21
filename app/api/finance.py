"""Moliya: to'lovlar, valyuta kursi, qarz hisoboti, qaytarish."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user, require_perm
from app.db import get_session
from app.models import Doctor, Order, Payment, Product, Return, Role, User
from app.permissions import (
    FX_EDIT,
    doctor_scope,
    PAYMENTS_CREATE,
    PAYMENTS_VIEW,
    RETURNS_CREATE,
    REPORTS_FINANCE,
    can,
)
from app.schemas import FxRateIn, OkOut, PaymentIn, PaymentOut, ReturnIn
from app.services import (
    contracts as contracts_service,
    debt as debt_service,
    fx as fx_service,
    inventory_ops,
    notifications,
    payments as payments_service,
    reports,
    stock as stock_service,
)
from app.utils.audit import log_action

router = APIRouter(prefix="/finance", tags=["finance"])


# ------------------------------------------------------------------ valyuta
@router.get("/fx")
async def current_rate(
    on_date: date | None = None,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
):
    rate = await fx_service.get_rate(session, on_date)
    return {"date": (on_date or fx_service.today_local()).isoformat(), "usd_uzs": rate}


@router.post("/fx", response_model=OkOut)
async def set_rate(
    payload: FxRateIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_perm(FX_EDIT)),
):
    old = await fx_service.get_rate(session, payload.rate_date)
    await fx_service.set_rate(session, payload.usd_uzs, payload.rate_date, user)
    await log_action(
        session, user, "set_rate", "fx", str(payload.rate_date or fx_service.today_local()),
        old={"usd_uzs": old}, new={"usd_uzs": payload.usd_uzs},
    )
    return OkOut(ok=True, message=f"Kurs saqlandi: 1 USD = {payload.usd_uzs:,.0f} so'm")


# ------------------------------------------------------------------ to'lovlar
@router.get("/payments", response_model=list[PaymentOut])
async def list_payments(
    doctor_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_perm(PAYMENTS_VIEW)),
):
    stmt = select(Payment).order_by(Payment.paid_at.desc()).limit(limit).offset(offset)
    if doctor_scope(user) is not None:
        stmt = stmt.where(Payment.agent_id == user.id)
    elif user.role is Role.DOCTOR:
        own = (
            await session.execute(select(Doctor.id).where(Doctor.user_id == user.id))
        ).scalar_one_or_none()
        stmt = stmt.where(Payment.doctor_id == (own or 0))
    if doctor_id is not None:
        stmt = stmt.where(Payment.doctor_id == doctor_id)
    if date_from is not None:
        stmt = stmt.where(Payment.paid_at >= reports.day_bounds(date_from)[0])
    if date_to is not None:
        stmt = stmt.where(Payment.paid_at <= reports.day_bounds(date_to)[1])

    rows = (await session.execute(stmt)).scalars().all()
    result = []
    for payment in rows:
        out = PaymentOut.model_validate(payment)
        doctor = await session.get(Doctor, payment.doctor_id)
        out.doctor_name = doctor.full_name if doctor else None
        if payment.order_id:
            order = await session.get(Order, payment.order_id)
            out.order_number = order.number if order else None
        if payment.received_by_id:
            receiver = await session.get(User, payment.received_by_id)
            out.received_by_name = receiver.full_name if receiver else None
        result.append(out)
    return result


@router.post("/payments", response_model=OkOut, status_code=201)
async def create_payment(
    payload: PaymentIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_perm(PAYMENTS_CREATE)),
):
    doctor = await session.get(Doctor, payload.doctor_id)
    if doctor is None:
        raise HTTPException(404, "Vrach topilmadi")
    if doctor_scope(user) is not None and doctor.agent_id != user.id:
        raise HTTPException(403, "Bu vrach sizga biriktirilmagan")

    try:
        payment, advance = await payments_service.create_payment(
            session,
            doctor=doctor,
            amount_uzs=payload.amount_uzs,
            method=payload.method,
            actor=user,
            order_id=payload.order_id,
            paid_at=payload.paid_at,
            fx_rate=payload.fx_rate,
            note=payload.note,
        )
    except payments_service.PaymentError as exc:
        raise HTTPException(400, str(exc)) from exc

    await log_action(
        session, user, "payment", "doctor", doctor.id,
        new={
            "amount_uzs": str(payment.amount_uzs),
            "amount_usd": str(payment.amount_usd),
            "method": payment.method.value,
        },
    )
    await notifications.payment_received(session, payment)

    # Shu to'lov taklif-shartnomani muddatida yopgan bo'lsa — tabrik.
    # Bu eng kuchli lahza: vrach sovg'ani his qilib, keyingi paketni oladi.
    sovgalar = await contracts_service.unnotified_gifts(session, doctor.id)
    for contract in sovgalar:
        await notifications.contract_gift_earned(session, contract)
        contract.gift_notified = True

    message = f"To'lov qabul qilindi: {payment.amount_uzs:,.0f} so'm (${payment.amount_usd})"
    if advance > 0:
        message += f". Avans qoldi: ${advance}"
    for contract in sovgalar:
        message += f"\n🎁 {contract.number} yopildi — sovg'a: {contract.gift_name}"
    return OkOut(ok=True, message=message.replace(",", " "))


# ---------------------------------------------------------------------- qarz
@router.get("/debts")
async def debts(
    only_overdue: bool = False,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_perm(PAYMENTS_VIEW)),
):
    """Vrachlar kesimida qarz va muddat."""
    agent_id = doctor_scope(user)
    rows = await reports.doctor_debt_rows(session, agent_id=agent_id)
    if only_overdue:
        rows = [r for r in rows if r["overdue_usd"] > 0]
    return rows


@router.get("/debts/aging")
async def aging(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_perm(REPORTS_FINANCE)),
):
    """Qarzning yoshlanishi: 0-30 / 31-60 / 61-90 / 90+ kun."""
    return await reports.debt_aging(session)


@router.get("/my-debt")
async def my_debt(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Vrachning o'z qarzi (vrach roli uchun)."""
    if user.role is not Role.DOCTOR:
        raise HTTPException(403, "Faqat vrachlar uchun")
    doctor = (
        await session.execute(select(Doctor).where(Doctor.user_id == user.id))
    ).scalar_one_or_none()
    if doctor is None:
        raise HTTPException(404, "Vrach kartochkangiz topilmadi")

    summary = await debt_service.doctor_debt(session, doctor.id)
    orders = (
        await session.execute(debt_service.unpaid_orders_stmt(doctor.id))
    ).scalars().all()
    today = fx_service.today_local()
    return {
        "total_usd": summary.total_usd,
        "overdue_usd": summary.overdue_usd,
        "not_due_usd": summary.not_due_usd,
        "debt_limit_usd": doctor.debt_limit_usd,
        "payment_term_days": doctor.payment_term_days,
        "orders": [
            {
                "number": o.number,
                "delivered_at": o.delivered_at.isoformat() if o.delivered_at else None,
                "due_date": o.due_date.isoformat() if o.due_date else None,
                "total_usd": o.total_usd,
                "paid_usd": o.paid_usd,
                "debt_usd": o.debt_usd,
                "overdue_days": (today - o.due_date).days
                if o.due_date and o.due_date < today
                else 0,
            }
            for o in orders
        ],
    }


# ---------------------------------------------------------------- qaytarish
@router.get("/returns")
async def list_returns(
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_perm(RETURNS_CREATE)),
):
    """Rasmiylashtirilgan qaytarishlar tarixi — yangisidan eskisiga."""
    stmt = (
        select(Return, Doctor.full_name, Order.number)
        .join(Doctor, Doctor.id == Return.doctor_id)
        .outerjoin(Order, Order.id == Return.order_id)
        .order_by(Return.id.desc())
        .limit(limit)
        .offset(offset)
    )
    # Agent faqat o'z hisobidan ayirilgan qaytarishlarni ko'radi
    if doctor_scope(user) is not None:
        stmt = stmt.where(Return.agent_id == user.id)

    rows = (await session.execute(stmt)).all()

    # Qaysi razmer qaytganini ko'rsatish uchun mahsulot nomlarini olamiz
    product_ids = {item.product_id for doc, _, _ in rows for item in doc.items}
    products: dict[int, Product] = {}
    if product_ids:
        found = (
            await session.execute(select(Product).where(Product.id.in_(product_ids)))
        ).scalars().all()
        products = {p.id: p for p in found}

    def _items(doc: Return) -> list[dict]:
        result = []
        for item in doc.items:
            product = products.get(item.product_id)
            result.append(
                {
                    "product_id": item.product_id,
                    "name": product.name if product else f"#{item.product_id}",
                    "size": product.size_label if product else None,
                    "implant_type": product.implant_type if product else None,
                    "qty": item.qty,
                    "line_total_usd": item.line_total_usd,
                }
            )
        return result

    return [
        {
            "id": doc.id,
            "number": doc.number,
            "doctor_name": doctor_name,
            "order_id": doc.order_id,
            "order_number": order_number,
            "total_usd": doc.total_usd,
            "units": sum(item.qty for item in doc.items),
            "reason": doc.reason,
            "created_at": doc.created_at.isoformat(),
            "items": _items(doc),
        }
        for doc, doctor_name, order_number in rows
    ]


@router.post("/returns", response_model=OkOut, status_code=201)
async def create_return(
    payload: ReturnIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_perm(RETURNS_CREATE)),
):
    doctor = await session.get(Doctor, payload.doctor_id)
    if doctor is None:
        raise HTTPException(404, "Vrach topilmadi")
    if doctor_scope(user) is not None and doctor.agent_id != user.id:
        raise HTTPException(403, "Bu vrach sizga biriktirilmagan")

    warehouse_id = payload.warehouse_id
    if warehouse_id is None:
        # Tovar qaytgan omborga qaytadi: buyurtma qaysi ombordan ketgan bo'lsa,
        # o'shanga. Aks holda markaziy omborga.
        if payload.order_id:
            order = await session.get(Order, payload.order_id)
            warehouse_id = order.warehouse_id if order else None
        if warehouse_id is None:
            warehouse_id = (await stock_service.main_warehouse(session)).id

    try:
        doc = await inventory_ops.create_return(
            session,
            doctor=doctor,
            warehouse_id=warehouse_id,
            lines=[(line.product_id, line.qty) for line in payload.lines],
            actor=user,
            order_id=payload.order_id,
            reason=payload.reason,
        )
    except (inventory_ops.InventoryOpError, stock_service.StockError) as exc:
        raise HTTPException(400, str(exc)) from exc

    await log_action(
        session, user, "return", "doctor", doctor.id,
        new={"number": doc.number, "total_usd": str(doc.total_usd)},
    )
    return OkOut(
        ok=True,
        message=(
            f"Qaytarish rasmiylashtirildi: {doc.number}\n"
            f"Summa ${doc.total_usd} — vrachning qarzidan ayirildi, "
            "tovar omborga qaytdi"
        ),
    )
