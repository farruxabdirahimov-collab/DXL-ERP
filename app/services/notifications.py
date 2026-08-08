"""Biznes hodisalari bo'yicha bildirishnomalar matni va manzili."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import notify
from app.models import (
    Doctor,
    Order,
    Payment,
    Product,
    Role,
    Stock,
    User,
    Warehouse,
)
from app.utils.fmt import fmt_short_date, money_usd, money_uzs, number


async def _doctor_label(session: AsyncSession, doctor_id: int) -> str:
    doctor = await session.get(Doctor, doctor_id)
    if doctor is None:
        return f"#{doctor_id}"
    clinic = f" ({doctor.clinic_name})" if doctor.clinic_name else ""
    return f"{doctor.full_name}{clinic}"


async def order_created(session: AsyncSession, order: Order) -> None:
    """Vrach buyurtma berdi -> agentga; agent kiritdi -> tasdiqlash kerak bo'lsa direktorga."""
    doctor = await _doctor_label(session, order.doctor_id)
    text = (
        f"🆕 <b>Yangi buyurtma {order.number}</b>\n"
        f"Vrach: {doctor}\n"
        f"Summa: {money_usd(order.total_usd)}\n"
        f"Mahsulot: {number(order.total_qty)} dona"
    )
    if order.needs_director:
        text += f"\n⚠️ Tasdiq kerak: {order.director_reason}"

    await notify.send_to_user_id(
        session,
        order.agent_id,
        text,
        kind="order_new",
        dedup_key=f"order_new:{order.id}",
        button=("Buyurtmani ochish", f"/orders/{order.id}"),
    )


async def order_needs_director(session: AsyncSession, order: Order) -> None:
    doctor = await _doctor_label(session, order.doctor_id)
    text = (
        f"⚠️ <b>Direktor tasdig'i kerak — {order.number}</b>\n"
        f"Vrach: {doctor}\n"
        f"Summa: {money_usd(order.total_usd)}\n"
        f"Sabab: {order.director_reason or '—'}"
    )
    await notify.send_to_roles(
        session,
        [Role.DIRECTOR, Role.SUPERADMIN],
        text,
        kind="order_director",
        dedup_key=f"order_director:{order.id}",
        button=("Ko'rib chiqish", f"/orders/{order.id}"),
    )


async def order_approved(session: AsyncSession, order: Order) -> None:
    """Tasdiqlandi -> omborchiga yig'ish uchun."""
    doctor = await _doctor_label(session, order.doctor_id)
    warehouse = await session.get(Warehouse, order.warehouse_id)
    text = (
        f"📦 <b>Yig'ish uchun buyurtma {order.number}</b>\n"
        f"Vrach: {doctor}\n"
        f"Ombor: {warehouse.name if warehouse else '—'}\n"
        f"Mahsulot: {number(order.total_qty)} dona"
    )
    await notify.send_to_roles(
        session,
        [Role.WAREHOUSE],
        text,
        kind="order_approved",
        dedup_key=f"order_approved:{order.id}",
        button=("Buyurtmani ochish", f"/orders/{order.id}"),
    )
    # Vrachga ham xabar beramiz
    doctor_obj = await session.get(Doctor, order.doctor_id)
    if doctor_obj and doctor_obj.user_id:
        await notify.send_to_user_id(
            session,
            doctor_obj.user_id,
            f"✅ Buyurtmangiz tasdiqlandi: <b>{order.number}</b>\n"
            f"Summa: {money_usd(order.total_usd)}",
            kind="order_approved_doctor",
            dedup_key=f"order_approved_doctor:{order.id}",
        )


async def order_delivered(session: AsyncSession, order: Order) -> None:
    doctor_obj = await session.get(Doctor, order.doctor_id)
    doctor = await _doctor_label(session, order.doctor_id)
    text = (
        f"🚚 <b>Yetkazildi — {order.number}</b>\n"
        f"Vrach: {doctor}\n"
        f"Summa: {money_usd(order.total_usd)}\n"
        f"To'lov muddati: {fmt_short_date(order.due_date)}"
    )
    await notify.send_to_roles(
        session,
        [Role.ACCOUNTANT],
        text,
        kind="order_delivered",
        dedup_key=f"order_delivered:{order.id}",
        button=("To'lov kiritish", f"/payments/new?doctor={order.doctor_id}"),
    )
    if doctor_obj and doctor_obj.user_id:
        await notify.send_to_user_id(
            session,
            doctor_obj.user_id,
            f"🚚 Buyurtmangiz yetkazildi: <b>{order.number}</b>\n"
            f"Summa: {money_usd(order.total_usd)}\n"
            f"To'lov muddati: {fmt_short_date(order.due_date)}",
            kind="order_delivered_doctor",
            dedup_key=f"order_delivered_doctor:{order.id}",
        )


async def order_cancelled(session: AsyncSession, order: Order) -> None:
    doctor_obj = await session.get(Doctor, order.doctor_id)
    text = (
        f"❌ Buyurtma bekor qilindi: <b>{order.number}</b>\n"
        f"Sabab: {order.cancel_reason or '—'}"
    )
    await notify.send_to_user_id(session, order.agent_id, text, kind="order_cancelled")
    if doctor_obj and doctor_obj.user_id:
        await notify.send_to_user_id(
            session, doctor_obj.user_id, text, kind="order_cancelled_doctor"
        )


async def payment_received(session: AsyncSession, payment: Payment) -> None:
    doctor = await _doctor_label(session, payment.doctor_id)
    text = (
        f"💰 <b>To'lov qabul qilindi</b>\n"
        f"Vrach: {doctor}\n"
        f"Summa: {money_uzs(payment.amount_uzs)} ({money_usd(payment.amount_usd)})\n"
        f"Kurs: {number(payment.fx_rate)}"
    )
    await notify.send_to_user_id(session, payment.agent_id, text, kind="payment")
    doctor_obj = await session.get(Doctor, payment.doctor_id)
    if doctor_obj and doctor_obj.user_id:
        await notify.send_to_user_id(
            session,
            doctor_obj.user_id,
            f"💰 To'lovingiz qabul qilindi: {money_uzs(payment.amount_uzs)}",
            kind="payment_doctor",
        )


async def check_low_stock(session: AsyncSession, product_ids: list[int]) -> None:
    """Qoldiq minimumdan pastga tushgan mahsulotlar haqida ogohlantirish."""
    from app.services.settings_service import get_setting

    if not product_ids or not bool(await get_setting(session, "low_stock_alerts")):
        return

    from sqlalchemy import func

    rows = (
        await session.execute(
            select(Product, func.coalesce(func.sum(Stock.qty), 0))
            .outerjoin(Stock, Stock.product_id == Product.id)
            .where(Product.id.in_(product_ids), Product.is_active.is_(True))
            .group_by(Product.id)
        )
    ).all()

    alerts = [
        f"{product.name} ({product.sku}) — {int(qty or 0)} dona qoldi "
        f"(minimum {product.min_stock})"
        for product, qty in rows
        if product.min_stock > 0 and int(qty or 0) <= product.min_stock
    ]
    if not alerts:
        return

    text = "🔔 <b>Omborda kam qoldi</b>\n" + "\n".join(f"  • {a}" for a in alerts[:15])
    await notify.send_to_roles(
        session,
        [Role.WAREHOUSE, Role.DIRECTOR, Role.SUPERADMIN],
        text,
        kind="low_stock",
        button=("Omborni ochish", "/stock"),
    )


async def welcome_new_user(session: AsyncSession, user: User) -> None:
    from app.models import ROLE_LABELS_UZ

    await notify.send_to_user(
        session,
        user,
        f"👋 Xush kelibsiz, <b>{user.full_name}</b>!\n"
        f"Sizning rolingiz: <b>{ROLE_LABELS_UZ[user.role]}</b>\n\n"
        "Ishni boshlash uchun quyidagi tugmani bosing.",
        kind="welcome",
        button=("DXL ERP ni ochish", "/"),
    )
