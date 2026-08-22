"""Foyda-zarar hisoboti.

Zanjir:
    sof sotuv − sotilgan tovar tannarxi = YALPI FOYDA
    yalpi foyda − xarajatlar − spisaniye − sovg'a = SOF FOYDA

Barcha raqamlar qaytarish ayirilgan holda: qaytarilgan tovar na sotuvda,
na tannarxda qoladi.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    EXPENSE_LABELS_UZ,
    Contract,
    Expense,
    GiftStatus,
    Order,
    OrderItem,
    OrderStatus,
    Return,
    ReturnItem,
    WriteOff,
    WriteOffItem,
)
from app.services.fx import round_money

ZERO = Decimal("0")


async def _cogs(session: AsyncSession, start: datetime, end: datetime) -> Decimal:
    """Sotilgan tovarning tannarxi (qaytarilgani ayirilgan)."""
    sotilgan = (
        await session.execute(
            select(func.coalesce(func.sum(OrderItem.cost_usd * OrderItem.qty), 0))
            .join(Order, Order.id == OrderItem.order_id)
            .where(
                Order.status == OrderStatus.DELIVERED,
                Order.delivered_at >= start,
                Order.delivered_at <= end,
            )
        )
    ).scalar_one()

    qaytgan = (
        await session.execute(
            select(func.coalesce(func.sum(ReturnItem.cost_usd * ReturnItem.qty), 0))
            .join(Return, Return.id == ReturnItem.return_id)
            .where(Return.created_at >= start, Return.created_at <= end)
        )
    ).scalar_one()

    return round_money(Decimal(sotilgan or 0) - Decimal(qaytgan or 0))


async def _writeoff_cost(
    session: AsyncSession, start: datetime, end: datetime
) -> Decimal:
    """Spisaniye qilingan tovar tannarxi — bu ham zarar."""
    total = (
        await session.execute(
            select(func.coalesce(func.sum(WriteOffItem.cost_usd * WriteOffItem.qty), 0))
            .join(WriteOff, WriteOff.id == WriteOffItem.writeoff_id)
            .where(WriteOff.created_at >= start, WriteOff.created_at <= end)
        )
    ).scalar_one()
    return round_money(Decimal(total or 0))


async def _gift_cost(session: AsyncSession, start: datetime, end: datetime) -> Decimal:
    """Berilgan sovg'alar tannarxi."""
    total = (
        await session.execute(
            select(func.coalesce(func.sum(Contract.gift_cost_usd), 0)).where(
                Contract.gift_status == GiftStatus.ISSUED,
                Contract.gift_issued_at >= start,
                Contract.gift_issued_at <= end,
            )
        )
    ).scalar_one()
    return round_money(Decimal(total or 0))


async def expenses_for_month(
    session: AsyncSession, year: int, month: int
) -> list[dict]:
    """Shu oyga tegishli xarajatlar, turlari bo'yicha yig'ilgan.

    Takrorlanadigan xarajat (ijara, oylik) bir marta kiritiladi va har oy
    hisobga olinadi.
    """
    rows = (await session.execute(select(Expense))).scalars().all()

    jamlanma: dict[str, Decimal] = {}
    for expense in rows:
        if not expense.active_in(year, month):
            continue
        kalit = expense.category.value
        jamlanma[kalit] = jamlanma.get(kalit, ZERO) + Decimal(expense.amount_usd)

    from app.models import ExpenseCategory

    return sorted(
        (
            {
                "category": kalit,
                "label": EXPENSE_LABELS_UZ[ExpenseCategory(kalit)],
                "amount_usd": round_money(summa),
            }
            for kalit, summa in jamlanma.items()
        ),
        key=lambda r: r["amount_usd"],
        reverse=True,
    )


async def monthly_report(
    session: AsyncSession, year: int, month: int
) -> dict:
    """Oylik foyda-zarar."""
    from app.services import reports as rp
    from app.services.plans import month_bounds

    start, end = month_bounds(year, month)
    sales = await rp.sales_summary(session, start, end)

    revenue = Decimal(sales["amount_usd"])
    cogs = await _cogs(session, start, end)
    gross = round_money(revenue - cogs)

    xarajatlar = await expenses_for_month(session, year, month)
    xarajat_jami = round_money(
        sum((Decimal(x["amount_usd"]) for x in xarajatlar), ZERO)
    )
    spisaniye = await _writeoff_cost(session, start, end)
    sovga = await _gift_cost(session, start, end)

    net = round_money(gross - xarajat_jami - spisaniye - sovga)

    def _pct(value: Decimal) -> float:
        return round(float(value / revenue * 100), 1) if revenue > 0 else 0.0

    return {
        "year": year,
        "month": month,
        # Daromad
        "revenue_usd": revenue,
        "units": sales["units"],
        "returned_usd": sales["returned_usd"],
        # Tannarx va yalpi foyda
        "cogs_usd": cogs,
        "gross_profit_usd": gross,
        "gross_margin_pct": _pct(gross),
        # Xarajatlar
        "expenses": xarajatlar,
        "expenses_total_usd": xarajat_jami,
        "writeoff_usd": spisaniye,
        "gift_usd": sovga,
        # Yakun
        "net_profit_usd": net,
        "net_margin_pct": _pct(net),
        # Pul bo'yicha: hisobda foyda bor, lekin qo'lga tekkanmi?
        "collected_usd": sales["collected_usd"],
        "uncollected_usd": round_money(revenue - Decimal(sales["collected_usd"])),
        # Tannarx kiritilmagan bo'lsa hisobot ishonchsiz — ogohlantiramiz
        "cost_missing": cogs <= 0 and revenue > 0,
    }


async def products_without_cost(session: AsyncSession) -> int:
    """Tannarxi kiritilmagan faol mahsulotlar soni."""
    from app.models import Product

    return int(
        (
            await session.execute(
                select(func.count(Product.id)).where(
                    Product.is_active.is_(True), Product.cost_usd <= 0
                )
            )
        ).scalar_one()
        or 0
    )
