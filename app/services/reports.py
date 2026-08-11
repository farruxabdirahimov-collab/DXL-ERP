"""Hisobotlar va tahlil: sotuv, mahsulot kesimlari, ombor, qarz, agentlar."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import Integer, and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import (
    Doctor,
    Return,
    ReturnItem,
    Order,
    OrderItem,
    OrderStatus,
    Payment,
    Product,
    ProductCategory,
    Role,
    Stock,
    StockMove,
    User,
    Warehouse,
)
from app.services.debt import total_debt
from app.services.fx import round_money, today_local
from app.services.settings_service import get_setting

ZERO = Decimal("0.00")


def day_bounds(day: date) -> tuple[datetime, datetime]:
    tz = settings.timezone
    return (
        datetime.combine(day, time.min, tzinfo=tz),
        datetime.combine(day, time.max, tzinfo=tz),
    )


def month_start(day: date) -> datetime:
    return datetime.combine(day.replace(day=1), time.min, tzinfo=settings.timezone)


def _returned_between(start: datetime, end: datetime):
    """Davr ichida rasmiylashtirilgan qaytarishlar."""
    return and_(Return.created_at >= start, Return.created_at <= end)


async def returns_summary(
    session: AsyncSession, start: datetime, end: datetime, agent_id: int | None = None
) -> dict:
    """Davrdagi qaytarishlar: summa va dona."""
    conditions = [_returned_between(start, end)]
    if agent_id is not None:
        conditions.append(Return.agent_id == agent_id)

    amount = (
        await session.execute(
            select(func.coalesce(func.sum(Return.total_usd), 0)).where(*conditions)
        )
    ).scalar_one()
    units = (
        await session.execute(
            select(func.coalesce(func.sum(ReturnItem.qty), 0))
            .join(Return, Return.id == ReturnItem.return_id)
            .where(*conditions)
        )
    ).scalar_one()
    count = (
        await session.execute(select(func.count(Return.id)).where(*conditions))
    ).scalar_one()

    return {
        "amount_usd": round_money(Decimal(amount or 0)),
        "units": int(units or 0),
        "count": int(count or 0),
    }


async def returned_by_product(
    session: AsyncSession, start: datetime, end: datetime
) -> dict[int, tuple[int, Decimal]]:
    """Mahsulot bo'yicha qaytarilgan dona va summa — tahlildan ayirish uchun."""
    rows = (
        await session.execute(
            select(
                ReturnItem.product_id,
                func.coalesce(func.sum(ReturnItem.qty), 0),
                func.coalesce(func.sum(ReturnItem.line_total_usd), 0),
            )
            .join(Return, Return.id == ReturnItem.return_id)
            .where(_returned_between(start, end))
            .group_by(ReturnItem.product_id)
        )
    ).all()
    return {int(pid): (int(qty or 0), Decimal(amount or 0)) for pid, qty, amount in rows}


def _delivered_between(start: datetime, end: datetime):
    return and_(
        Order.status == OrderStatus.DELIVERED,
        Order.delivered_at >= start,
        Order.delivered_at <= end,
    )


async def sales_summary(
    session: AsyncSession, start: datetime, end: datetime, agent_id: int | None = None
) -> dict:
    """Davr bo'yicha sotuv: summa, dona, buyurtmalar soni, vrachlar soni."""
    conditions = [_delivered_between(start, end)]
    if agent_id is not None:
        conditions.append(Order.agent_id == agent_id)

    amount, orders_count, doctors_count = (
        await session.execute(
            select(
                func.coalesce(func.sum(Order.total_usd), 0),
                func.count(Order.id),
                func.count(func.distinct(Order.doctor_id)),
            ).where(*conditions)
        )
    ).one()

    units = (
        await session.execute(
            select(func.coalesce(func.sum(OrderItem.qty), 0))
            .join(Order, Order.id == OrderItem.order_id)
            .where(*conditions)
        )
    ).scalar_one()

    pay_conditions = [Payment.paid_at >= start, Payment.paid_at <= end]
    if agent_id is not None:
        pay_conditions.append(Payment.agent_id == agent_id)
    collected = (
        await session.execute(
            select(func.coalesce(func.sum(Payment.amount_usd), 0)).where(*pay_conditions)
        )
    ).scalar_one()

    returned = await returns_summary(session, start, end, agent_id)
    gross = round_money(Decimal(amount or 0))
    gross_units = int(units or 0)

    return {
        # Sof ko'rsatkichlar — qaytarishlar ayirilgan (asosiy raqamlar shular)
        "amount_usd": round_money(gross - returned["amount_usd"]),
        "units": gross_units - returned["units"],
        # Batafsil ko'rish uchun
        "gross_amount_usd": gross,
        "gross_units": gross_units,
        "returned_usd": returned["amount_usd"],
        "returned_units": returned["units"],
        "returns_count": returned["count"],
        "orders": int(orders_count or 0),
        "doctors": int(doctors_count or 0),
        "collected_usd": round_money(Decimal(collected or 0)),
    }


# --------------------------------------------------------------------------
# Mahsulot tahlili
# --------------------------------------------------------------------------


async def top_products(
    session: AsyncSession,
    start: datetime,
    end: datetime,
    *,
    limit: int = 20,
    ascending: bool = False,
) -> list[dict]:
    """Eng ko'p (yoki eng kam) sotilgan mahsulotlar."""
    qty_sum = func.coalesce(func.sum(OrderItem.qty), 0).label("qty")
    amount_sum = func.coalesce(func.sum(OrderItem.line_total_usd), 0).label("amount")

    rows = (
        await session.execute(
            select(
                Product.id,
                Product.sku,
                Product.name,
                Product.diameter_mm,
                Product.length_mm,
                Product.implant_type,
                qty_sum,
                amount_sum,
            )
            .join(OrderItem, OrderItem.product_id == Product.id)
            .join(Order, Order.id == OrderItem.order_id)
            .where(_delivered_between(start, end))
            .group_by(
                Product.id,
                Product.sku,
                Product.name,
                Product.diameter_mm,
                Product.length_mm,
                Product.implant_type,
            )
            .order_by(qty_sum.asc() if ascending else qty_sum.desc())
            .limit(limit)
        )
    ).all()

    returned = await returned_by_product(session, start, end)
    result = []
    for r in rows:
        back_qty, back_amount = returned.get(int(r.id), (0, Decimal("0")))
        result.append(
            {
                "product_id": r.id,
                "sku": r.sku,
                "name": r.name,
                "size": _size_label(r.diameter_mm, r.length_mm),
                "implant_type": r.implant_type,
                "qty": max(0, int(r.qty or 0) - back_qty),
                "amount_usd": round_money(
                    max(Decimal("0"), Decimal(r.amount or 0) - back_amount)
                ),
                "returned_qty": back_qty,
            }
        )
    # Qaytarishdan keyin tartib o'zgarishi mumkin
    result.sort(key=lambda row: row["qty"], reverse=not ascending)
    return result


def _size_label(diameter, length) -> str:
    if diameter is None or length is None:
        return "—"
    return f"{float(diameter):g} x {float(length):g}"


def _as_aware(value: datetime | None) -> datetime | None:
    """SQLite naive datetime qaytaradi — vaqt zonasini qo'shamiz."""
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=settings.timezone)


async def size_demand(
    session: AsyncSession,
    start: datetime,
    end: datetime,
    limit: int = 40,
    category_code: str | None = "implant",
) -> list[dict]:
    """Eng talabgir implant razmerlari (diametr x uzunlik kesimida)."""
    qty_sum = func.coalesce(func.sum(OrderItem.qty), 0).label("qty")
    amount_sum = func.coalesce(func.sum(OrderItem.line_total_usd), 0).label("amount")

    stmt = (
        select(Product.diameter_mm, Product.length_mm, qty_sum, amount_sum)
        .join(OrderItem, OrderItem.product_id == Product.id)
        .join(Order, Order.id == OrderItem.order_id)
        .where(
            _delivered_between(start, end),
            Product.diameter_mm.is_not(None),
            Product.length_mm.is_not(None),
        )
        .group_by(Product.diameter_mm, Product.length_mm)
        .order_by(qty_sum.desc())
        .limit(limit)
    )
    if category_code:
        stmt = stmt.join(
            ProductCategory, ProductCategory.id == Product.category_id
        ).where(ProductCategory.code == category_code)

    rows = (await session.execute(stmt)).all()

    # Qaytarilgan donalarni razmer kesimida ayiramiz
    returned = await returned_by_product(session, start, end)
    sizes: dict[tuple, int] = {}
    if returned:
        product_rows = (
            await session.execute(
                select(Product.id, Product.diameter_mm, Product.length_mm).where(
                    Product.id.in_(list(returned))
                )
            )
        ).all()
        for pid, diameter, length in product_rows:
            if diameter is None or length is None:
                continue
            key = (float(diameter), float(length))
            sizes[key] = sizes.get(key, 0) + returned[int(pid)][0]

    result = []
    for r in rows:
        key = (float(r.diameter_mm), float(r.length_mm))
        qty = max(0, int(r.qty or 0) - sizes.get(key, 0))
        if qty == 0:
            continue
        result.append(
            {
                "diameter_mm": float(r.diameter_mm),
                "length_mm": float(r.length_mm),
                "size": _size_label(r.diameter_mm, r.length_mm),
                "qty": qty,
                "amount_usd": round_money(Decimal(r.amount or 0)),
            }
        )
    result.sort(key=lambda row: row["qty"], reverse=True)
    return result


async def sales_by_type(
    session: AsyncSession, start: datetime, end: datetime
) -> list[dict]:
    """Implant turi kesimida sotuv ulushi."""
    qty_sum = func.coalesce(func.sum(OrderItem.qty), 0).label("qty")
    amount_sum = func.coalesce(func.sum(OrderItem.line_total_usd), 0).label("amount")
    label = func.coalesce(Product.implant_type, "Boshqa").label("type_name")

    rows = (
        await session.execute(
            select(label, qty_sum, amount_sum)
            .join(OrderItem, OrderItem.product_id == Product.id)
            .join(Order, Order.id == OrderItem.order_id)
            .where(_delivered_between(start, end))
            .group_by(label)
            .order_by(qty_sum.desc())
        )
    ).all()
    return [
        {
            "implant_type": r.type_name,
            "qty": int(r.qty or 0),
            "amount_usd": round_money(Decimal(r.amount or 0)),
        }
        for r in rows
    ]


async def stock_by_product(
    session: AsyncSession, warehouse_id: int | None = None
) -> list[dict]:
    """Har mahsulot bo'yicha umumiy qoldiq (yoki bitta ombor kesimida)."""
    qty_sum = func.coalesce(func.sum(Stock.qty), 0).label("qty")
    reserved_sum = func.coalesce(func.sum(Stock.reserved_qty), 0).label("reserved")

    stmt = (
        select(
            Product.id,
            Product.sku,
            Product.name,
            Product.min_stock,
            Product.price_usd,
            Product.diameter_mm,
            Product.length_mm,
            ProductCategory.name_uz.label("category"),
            qty_sum,
            reserved_sum,
        )
        .join(ProductCategory, ProductCategory.id == Product.category_id)
        .outerjoin(Stock, Stock.product_id == Product.id)
        .where(Product.is_active.is_(True))
        .group_by(
            Product.id,
            Product.sku,
            Product.name,
            Product.min_stock,
            Product.price_usd,
            Product.diameter_mm,
            Product.length_mm,
            ProductCategory.name_uz,
        )
        .order_by(Product.name)
    )
    if warehouse_id is not None:
        stmt = stmt.where(Stock.warehouse_id == warehouse_id)

    rows = (await session.execute(stmt)).all()
    return [
        {
            "product_id": r.id,
            "sku": r.sku,
            "name": r.name,
            "category": r.category,
            "size": _size_label(r.diameter_mm, r.length_mm),
            "qty": int(r.qty or 0),
            "reserved": int(r.reserved or 0),
            "available": int(r.qty or 0) - int(r.reserved or 0),
            "min_stock": int(r.min_stock or 0),
            "price_usd": round_money(Decimal(r.price_usd or 0)),
            "value_usd": round_money(Decimal(r.qty or 0) * Decimal(r.price_usd or 0)),
        }
        for r in rows
    ]


async def daily_consumption(session: AsyncSession, days: int = 30) -> dict[int, float]:
    """Oxirgi `days` kun ichidagi o'rtacha kunlik sarf (dona/kun)."""
    since = datetime.now(tz=settings.timezone) - timedelta(days=days)
    rows = (
        await session.execute(
            select(OrderItem.product_id, func.coalesce(func.sum(OrderItem.qty), 0))
            .join(Order, Order.id == OrderItem.order_id)
            .where(Order.status == OrderStatus.DELIVERED, Order.delivered_at >= since)
            .group_by(OrderItem.product_id)
        )
    ).all()
    return {int(pid): float(qty or 0) / days for pid, qty in rows}


async def low_stock(session: AsyncSession) -> list[dict]:
    """Omborda kam qolgan mahsulotlar + necha kunga yetishi."""
    rows = await stock_by_product(session)
    consumption = await daily_consumption(session)
    result = []
    for row in rows:
        if row["qty"] > row["min_stock"]:
            continue
        per_day = consumption.get(row["product_id"], 0.0)
        row = dict(row)
        row["shortage"] = max(0, row["min_stock"] - row["qty"])
        row["days_left"] = round(row["qty"] / per_day, 1) if per_day > 0 else None
        row["avg_daily"] = round(per_day, 2)
        result.append(row)
    result.sort(key=lambda r: (r["qty"], -(r["avg_daily"] or 0)))
    return result


async def out_of_stock(session: AsyncSession) -> list[dict]:
    rows = await stock_by_product(session)
    consumption = await daily_consumption(session, days=90)
    result = []
    for row in rows:
        if row["qty"] > 0:
            continue
        row = dict(row)
        row["avg_daily"] = round(consumption.get(row["product_id"], 0.0), 2)
        result.append(row)
    # Talabi bori birinchi turadi
    result.sort(key=lambda r: r["avg_daily"], reverse=True)
    return result


async def dead_stock(session: AsyncSession, days: int | None = None) -> list[dict]:
    """Belgilangan kun ichida umuman sotilmagan, lekin omborda turgan mahsulotlar."""
    days = days or int(await get_setting(session, "dead_stock_days") or 90)
    since = datetime.now(tz=settings.timezone) - timedelta(days=days)

    sold_ids = set(
        (
            await session.execute(
                select(func.distinct(OrderItem.product_id))
                .join(Order, Order.id == OrderItem.order_id)
                .where(Order.status == OrderStatus.DELIVERED, Order.delivered_at >= since)
            )
        )
        .scalars()
        .all()
    )

    last_sale = dict(
        (
            await session.execute(
                select(OrderItem.product_id, func.max(Order.delivered_at))
                .join(Order, Order.id == OrderItem.order_id)
                .where(Order.status == OrderStatus.DELIVERED)
                .group_by(OrderItem.product_id)
            )
        ).all()
    )

    rows = await stock_by_product(session)
    result = []
    for row in rows:
        if row["product_id"] in sold_ids or row["qty"] <= 0:
            continue
        row = dict(row)
        sold_at = _as_aware(last_sale.get(row["product_id"]))
        row["last_sale_at"] = sold_at.isoformat() if sold_at else None
        row["days_idle"] = (
            (datetime.now(tz=settings.timezone) - sold_at).days if sold_at else None
        )
        result.append(row)
    result.sort(key=lambda r: r["value_usd"], reverse=True)
    return result


# --------------------------------------------------------------------------
# Vrachlar / qarz / agentlar
# --------------------------------------------------------------------------


async def doctor_debt_rows(
    session: AsyncSession, on_date: date | None = None, agent_id: int | None = None
) -> list[dict]:
    """Har vrach bo'yicha qarz, muddati o'tgan qism va eng eski muddat."""
    on_date = on_date or today_local()
    debt_expr = Order.total_usd - Order.paid_usd - Order.returned_usd
    overdue_expr = case((Order.due_date < on_date, debt_expr), else_=0)

    rows = (
        await session.execute(
            select(
                Doctor.id,
                Doctor.full_name,
                Doctor.clinic_name,
                Doctor.phone,
                Doctor.category,
                Doctor.loyalty_score,
                Doctor.debt_limit_usd,
                Doctor.payment_term_days,
                Doctor.agent_id,
                func.coalesce(func.sum(debt_expr), 0).label("debt"),
                func.coalesce(func.sum(overdue_expr), 0).label("overdue"),
                func.min(Order.due_date).label("oldest_due"),
                func.count(Order.id).label("open_orders"),
            )
            .join(Order, Order.doctor_id == Doctor.id)
            .where(Order.status == OrderStatus.DELIVERED, debt_expr > Decimal("0.005"))
            .group_by(
                Doctor.id,
                Doctor.full_name,
                Doctor.clinic_name,
                Doctor.phone,
                Doctor.category,
                Doctor.loyalty_score,
                Doctor.debt_limit_usd,
                Doctor.payment_term_days,
                Doctor.agent_id,
            )
            .having(func.coalesce(func.sum(debt_expr), 0) > Decimal("0.005"))
        )
    ).all()

    result = []
    for r in rows:
        if agent_id is not None and r.agent_id != agent_id:
            continue
        oldest = r.oldest_due
        result.append(
            {
                "doctor_id": r.id,
                "full_name": r.full_name,
                "clinic_name": r.clinic_name,
                "phone": r.phone,
                "category": r.category.value if r.category else None,
                "loyalty_score": r.loyalty_score,
                "debt_usd": round_money(Decimal(r.debt or 0)),
                "overdue_usd": round_money(Decimal(r.overdue or 0)),
                "debt_limit_usd": round_money(Decimal(r.debt_limit_usd or 0)),
                "payment_term_days": r.payment_term_days,
                "oldest_due_date": oldest.isoformat() if oldest else None,
                "overdue_days": (on_date - oldest).days if oldest and oldest < on_date else 0,
                "open_orders": int(r.open_orders or 0),
                "agent_id": r.agent_id,
            }
        )
    result.sort(key=lambda r: (r["overdue_usd"], r["debt_usd"]), reverse=True)
    return result


async def debt_aging(session: AsyncSession, on_date: date | None = None) -> dict:
    """Qarzning yoshlanishi: 0-30 / 31-60 / 61-90 / 90+ kun."""
    on_date = on_date or today_local()
    debt_expr = Order.total_usd - Order.paid_usd - Order.returned_usd

    rows = (
        await session.execute(
            select(Order.due_date, debt_expr.label("debt")).where(
                Order.status == OrderStatus.DELIVERED, debt_expr > Decimal("0.005")
            )
        )
    ).all()

    buckets = {
        "muddati kelmagan": ZERO,
        "0-30 kun": ZERO,
        "31-60 kun": ZERO,
        "61-90 kun": ZERO,
        "90+ kun": ZERO,
    }
    for due, debt in rows:
        value = round_money(Decimal(debt or 0))
        if due is None:
            buckets["0-30 kun"] += value
            continue
        overdue_days = (on_date - due).days
        if overdue_days <= 0:
            buckets["muddati kelmagan"] += value
        elif overdue_days <= 30:
            buckets["0-30 kun"] += value
        elif overdue_days <= 60:
            buckets["31-60 kun"] += value
        elif overdue_days <= 90:
            buckets["61-90 kun"] += value
        else:
            buckets["90+ kun"] += value

    return {name: round_money(value) for name, value in buckets.items()}


async def agent_rows(
    session: AsyncSession, start: datetime, end: datetime
) -> list[dict]:
    """Agentlar kesimida sotuv va yig'ilgan pul."""
    agents = (
        await session.execute(
            select(User).where(User.role == Role.AGENT, User.is_active.is_(True))
        )
    ).scalars().all()

    result = []
    for agent in agents:
        summary = await sales_summary(session, start, end, agent_id=agent.id)
        doctors_count = (
            await session.execute(
                select(func.count(Doctor.id)).where(
                    Doctor.agent_id == agent.id, Doctor.is_active.is_(True)
                )
            )
        ).scalar_one()
        result.append(
            {
                "user_id": agent.id,
                "full_name": agent.full_name,
                "doctors": int(doctors_count or 0),
                **summary,
            }
        )
    result.sort(key=lambda r: r["amount_usd"], reverse=True)
    return result


# --------------------------------------------------------------------------
# Dashboard va kunlik statistika
# --------------------------------------------------------------------------


async def dashboard(session: AsyncSession, on_date: date | None = None) -> dict:
    on_date = on_date or today_local()
    day_start, day_end = day_bounds(on_date)
    m_start = month_start(on_date)

    today_sales = await sales_summary(session, day_start, day_end)
    month_sales = await sales_summary(session, m_start, day_end)
    debt = await total_debt(session, on_date)

    low = await low_stock(session)
    empty = [row for row in low if row["qty"] == 0]

    new_doctors_today = (
        await session.execute(
            select(func.count(Doctor.id)).where(
                Doctor.created_at >= day_start, Doctor.created_at <= day_end
            )
        )
    ).scalar_one()

    pending = (
        await session.execute(
            select(Order.status, func.count(Order.id))
            .where(
                Order.status.in_(
                    [
                        OrderStatus.NEW,
                        OrderStatus.DIRECTOR_REVIEW,
                        OrderStatus.APPROVED,
                        OrderStatus.PICKING,
                        OrderStatus.SHIPPED,
                    ]
                )
            )
            .group_by(Order.status)
        )
    ).all()

    stock_value = (
        await session.execute(
            select(func.coalesce(func.sum(Stock.qty * Product.price_usd), 0)).join(
                Product, Product.id == Stock.product_id
            )
        )
    ).scalar_one()

    return {
        "date": on_date.isoformat(),
        "today": today_sales,
        "month": month_sales,
        "debt": debt,
        "low_stock_count": len(low),
        "out_of_stock_count": len(empty),
        "new_doctors_today": int(new_doctors_today or 0),
        "pending_orders": {status.value: int(count) for status, count in pending},
        "stock_value_usd": round_money(Decimal(stock_value or 0)),
    }


async def warehouse_day_summary(session: AsyncSession, on_date: date) -> dict:
    """Omborchi uchun: kunlik kirim/chiqim va kutayotgan buyurtmalar."""
    start, end = day_bounds(on_date)
    rows = (
        await session.execute(
            select(StockMove.kind, func.coalesce(func.sum(StockMove.qty), 0))
            .where(StockMove.created_at >= start, StockMove.created_at <= end)
            .group_by(StockMove.kind)
        )
    ).all()
    moves = {kind.value: int(qty or 0) for kind, qty in rows}

    waiting = (
        await session.execute(
            select(func.count(Order.id)).where(
                Order.status.in_([OrderStatus.APPROVED, OrderStatus.PICKING])
            )
        )
    ).scalar_one()

    return {"moves": moves, "waiting_orders": int(waiting or 0)}


async def stock_by_warehouse(session: AsyncSession) -> list[dict]:
    rows = (
        await session.execute(
            select(
                Warehouse.id,
                Warehouse.name,
                Warehouse.kind,
                func.coalesce(func.sum(Stock.qty), 0).label("qty"),
                func.coalesce(func.sum(Stock.qty * Product.price_usd), 0).label("value"),
                func.count(func.distinct(case((Stock.qty > 0, Stock.product_id)))).label("skus"),
            )
            .outerjoin(Stock, Stock.warehouse_id == Warehouse.id)
            .outerjoin(Product, Product.id == Stock.product_id)
            .where(Warehouse.is_active.is_(True))
            .group_by(Warehouse.id, Warehouse.name, Warehouse.kind)
            .order_by(Warehouse.kind, Warehouse.name)
        )
    ).all()
    return [
        {
            "warehouse_id": r.id,
            "name": r.name,
            "kind": r.kind.value,
            "qty": int(r.qty or 0),
            "skus": int(r.skus or 0),
            "value_usd": round_money(Decimal(r.value or 0)),
        }
        for r in rows
    ]


async def new_doctors_count(
    session: AsyncSession, start: datetime, end: datetime, agent_id: int | None = None
) -> int:
    stmt = select(func.count(Doctor.id)).where(
        Doctor.created_at >= start, Doctor.created_at <= end
    )
    if agent_id is not None:
        stmt = stmt.where(Doctor.agent_id == agent_id)
    return int((await session.execute(stmt)).scalar_one() or 0)


async def payments_summary(
    session: AsyncSession, start: datetime, end: datetime
) -> dict:
    rows = (
        await session.execute(
            select(
                Payment.method,
                func.coalesce(func.sum(Payment.amount_usd), 0),
                func.coalesce(func.sum(Payment.amount_uzs), 0),
                func.count(Payment.id),
            )
            .where(Payment.paid_at >= start, Payment.paid_at <= end)
            .group_by(Payment.method)
        )
    ).all()
    total_usd = ZERO
    total_uzs = ZERO
    by_method = {}
    for method, usd, uzs, count in rows:
        total_usd += Decimal(usd or 0)
        total_uzs += Decimal(uzs or 0)
        by_method[method.value] = {
            "amount_usd": round_money(Decimal(usd or 0)),
            "amount_uzs": round_money(Decimal(uzs or 0)),
            "count": int(count),
        }
    return {
        "total_usd": round_money(total_usd),
        "total_uzs": round_money(total_uzs),
        "by_method": by_method,
    }


async def sales_trend(session: AsyncSession, days: int = 30) -> list[dict]:
    """Oxirgi kunlar bo'yicha sotuv grafigi uchun ma'lumot."""
    today = today_local()
    start = datetime.combine(today - timedelta(days=days - 1), time.min, tzinfo=settings.timezone)
    end = datetime.combine(today, time.max, tzinfo=settings.timezone)

    rows = (
        await session.execute(
            select(Order.delivered_at, Order.total_usd).where(
                _delivered_between(start, end)
            )
        )
    ).all()

    totals: dict[str, Decimal] = {}
    for delivered_at, amount in rows:
        key = _as_aware(delivered_at).astimezone(settings.timezone).date().isoformat()
        totals[key] = totals.get(key, ZERO) + Decimal(amount or 0)

    result = []
    for offset in range(days):
        day = today - timedelta(days=days - 1 - offset)
        key = day.isoformat()
        result.append({"date": key, "amount_usd": round_money(totals.get(key, ZERO))})
    return result


async def stock_moves_journal(
    session: AsyncSession,
    *,
    limit: int = 100,
    warehouse_id: int | None = None,
    product_id: int | None = None,
) -> list[dict]:
    stmt = (
        select(StockMove, Product.name, Product.sku, User.full_name)
        .join(Product, Product.id == StockMove.product_id)
        .outerjoin(User, User.id == StockMove.user_id)
        .order_by(StockMove.id.desc())
        .limit(limit)
    )
    if warehouse_id is not None:
        stmt = stmt.where(
            (StockMove.from_warehouse_id == warehouse_id)
            | (StockMove.to_warehouse_id == warehouse_id)
        )
    if product_id is not None:
        stmt = stmt.where(StockMove.product_id == product_id)

    rows = (await session.execute(stmt)).all()
    return [
        {
            "id": move.id,
            "created_at": move.created_at.isoformat(),
            "kind": move.kind.value,
            "product": f"{sku} — {name}",
            "qty": move.qty,
            "from_warehouse_id": move.from_warehouse_id,
            "to_warehouse_id": move.to_warehouse_id,
            "doc_type": move.doc_type,
            "doc_id": move.doc_id,
            "user": user_name,
            "note": move.note,
        }
        for move, name, sku, user_name in rows
    ]


async def category_breakdown(
    session: AsyncSession, start: datetime, end: datetime
) -> list[dict]:
    qty_sum = func.coalesce(func.sum(OrderItem.qty), 0).label("qty")
    amount_sum = func.coalesce(func.sum(OrderItem.line_total_usd), 0).label("amount")
    rows = (
        await session.execute(
            select(ProductCategory.name_uz, qty_sum, amount_sum)
            .join(Product, Product.category_id == ProductCategory.id)
            .join(OrderItem, OrderItem.product_id == Product.id)
            .join(Order, Order.id == OrderItem.order_id)
            .where(_delivered_between(start, end))
            .group_by(ProductCategory.name_uz)
            .order_by(amount_sum.desc())
        )
    ).all()
    return [
        {
            "category": name,
            "qty": int(qty or 0),
            "amount_usd": round_money(Decimal(amount or 0)),
        }
        for name, qty, amount in rows
    ]


async def doctor_rows(
    session: AsyncSession, agent_id: int | None = None
) -> list[dict]:
    """Vrachlar ro'yxati — xarid darajasi, sodiqlik, oxirgi xarid, qarz."""
    debts = {row["doctor_id"]: row for row in await doctor_debt_rows(session)}
    stmt = select(Doctor).where(Doctor.is_active.is_(True))
    if agent_id is not None:
        stmt = stmt.where(Doctor.agent_id == agent_id)
    doctors = (await session.execute(stmt.order_by(Doctor.full_name))).scalars().all()

    result = []
    for doctor in doctors:
        debt = debts.get(doctor.id, {})
        result.append(
            {
                "doctor_id": doctor.id,
                "full_name": doctor.full_name,
                "clinic_name": doctor.clinic_name,
                "phone": doctor.phone,
                "region": doctor.region,
                "birth_date": doctor.birth_date.isoformat() if doctor.birth_date else None,
                "category": doctor.category.value,
                "loyalty_score": doctor.loyalty_score,
                "purchased_12m_usd": round_money(Decimal(doctor.purchased_12m_usd or 0)),
                "orders_12m": doctor.orders_12m,
                "last_order_at": doctor.last_order_at.isoformat()
                if doctor.last_order_at
                else None,
                "debt_usd": debt.get("debt_usd", ZERO),
                "overdue_usd": debt.get("overdue_usd", ZERO),
                "debt_limit_usd": round_money(Decimal(doctor.debt_limit_usd or 0)),
                "agent_id": doctor.agent_id,
            }
        )
    return result
