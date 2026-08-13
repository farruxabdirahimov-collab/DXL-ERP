"""Vrachning mini hisoboti: nima oldi, qaysi razmerda, nimani qaytardi, qancha to'ladi.

Vrach kartochkasida bitta ekranda ko'rinadigan to'rt ko'rsatkich shu yerda
yig'iladi. Raqamlar boshqa hisobotlar bilan bir xil qoidada: qaytarilgan
tovar xariddan ayiriladi, ya'ni "sof" ko'rsatkich chiqadi.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    METHOD_LABELS_UZ,
    Order,
    OrderItem,
    OrderStatus,
    Payment,
    Product,
    Return,
    ReturnItem,
)
from app.services.fx import round_money

ZERO = Decimal("0")


@dataclass
class SizeRow:
    """Bitta razmer kesimida: qancha olgan, qancha qaytargan."""

    size: str
    implant_type: str | None
    bought_qty: int = 0
    returned_qty: int = 0
    amount_usd: Decimal = ZERO

    @property
    def net_qty(self) -> int:
        return self.bought_qty - self.returned_qty


@dataclass
class Event:
    """Tarixdagi bitta voqea: xarid, qaytarish yoki to'lov."""

    kind: str  # order | return | payment
    at: str
    number: str
    amount_usd: Decimal
    note: str | None = None
    order_id: int | None = None
    lines: list[dict] = field(default_factory=list)


def _iso(value) -> str:
    return value.isoformat() if value is not None else ""


async def build(session: AsyncSession, doctor_id: int, limit: int = 60) -> dict:
    """Vrachning to'liq tranzaksiyalar tarixi va razmerlar kesimi."""
    orders = (
        await session.execute(
            select(Order)
            .where(Order.doctor_id == doctor_id, Order.status == OrderStatus.DELIVERED)
            .order_by(Order.delivered_at.desc())
        )
    ).scalars().all()

    returns = (
        await session.execute(
            select(Return)
            .where(Return.doctor_id == doctor_id)
            .order_by(Return.created_at.desc())
        )
    ).scalars().all()

    payments = (
        await session.execute(
            select(Payment)
            .where(Payment.doctor_id == doctor_id)
            .order_by(Payment.paid_at.desc())
        )
    ).scalars().all()

    # Kerakli mahsulotlarni bir marta o'qiymiz
    product_ids = {item.product_id for o in orders for item in o.items}
    product_ids |= {item.product_id for r in returns for item in r.items}
    products: dict[int, Product] = {}
    if product_ids:
        found = (
            await session.execute(select(Product).where(Product.id.in_(product_ids)))
        ).scalars().all()
        products = {p.id: p for p in found}

    def _key(product_id: int) -> tuple[str, str | None]:
        product = products.get(product_id)
        if product is None:
            return (f"#{product_id}", None)
        return (product.size_label, product.implant_type)

    sizes: dict[tuple[str, str | None], SizeRow] = {}

    def _row(product_id: int) -> SizeRow:
        key = _key(product_id)
        if key not in sizes:
            sizes[key] = SizeRow(size=key[0], implant_type=key[1])
        return sizes[key]

    events: list[Event] = []

    bought_usd = ZERO
    bought_units = 0
    for order in orders:
        lines = []
        for item in order.items:
            row = _row(item.product_id)
            row.bought_qty += item.qty
            row.amount_usd += Decimal(item.line_total_usd)
            bought_units += item.qty
            lines.append({"size": _key(item.product_id)[0], "qty": item.qty})
        bought_usd += Decimal(order.total_usd)
        events.append(
            Event(
                kind="order",
                at=_iso(order.delivered_at),
                number=order.number,
                amount_usd=round_money(Decimal(order.total_usd)),
                order_id=order.id,
                lines=lines,
            )
        )

    returned_usd = ZERO
    returned_units = 0
    for doc in returns:
        lines = []
        for item in doc.items:
            row = _row(item.product_id)
            row.returned_qty += item.qty
            row.amount_usd -= Decimal(item.line_total_usd)
            returned_units += item.qty
            lines.append({"size": _key(item.product_id)[0], "qty": item.qty})
        returned_usd += Decimal(doc.total_usd)
        events.append(
            Event(
                kind="return",
                at=_iso(doc.created_at),
                number=doc.number,
                amount_usd=round_money(Decimal(doc.total_usd)),
                note=doc.reason,
                order_id=doc.order_id,
                lines=lines,
            )
        )

    paid_usd = ZERO
    for payment in payments:
        paid_usd += Decimal(payment.amount_usd)
        # To'lovda hujjat raqami yo'q — so'mdagi summani izohga chiqaramiz
        method = METHOD_LABELS_UZ.get(payment.method, payment.method.value)
        events.append(
            Event(
                kind="payment",
                at=_iso(payment.paid_at),
                number=f"To'lov #{payment.id}",
                amount_usd=round_money(Decimal(payment.amount_usd)),
                note=f"{method} · {Decimal(payment.amount_uzs):,.0f} so'm".replace(
                    ",", " "
                ),
                order_id=payment.order_id,
            )
        )

    events.sort(key=lambda e: e.at, reverse=True)

    size_rows = sorted(
        sizes.values(), key=lambda r: (r.net_qty, r.bought_qty), reverse=True
    )

    return {
        "summary": {
            "orders_count": len(orders),
            "returns_count": len(returns),
            "payments_count": len(payments),
            "bought_units": bought_units,
            "returned_units": returned_units,
            "net_units": bought_units - returned_units,
            "bought_usd": round_money(bought_usd),
            "returned_usd": round_money(returned_usd),
            # Sof xarid — hisobotlardagi "xarid darajasi" bilan bir xil qoida
            "net_usd": round_money(bought_usd - returned_usd),
            "paid_usd": round_money(paid_usd),
            "debt_usd": round_money(bought_usd - returned_usd - paid_usd),
            "first_order_at": _iso(orders[-1].delivered_at) if orders else None,
            "last_order_at": _iso(orders[0].delivered_at) if orders else None,
        },
        "sizes": [
            {
                "size": r.size,
                "implant_type": r.implant_type,
                "bought_qty": r.bought_qty,
                "returned_qty": r.returned_qty,
                "net_qty": r.net_qty,
                "amount_usd": round_money(r.amount_usd),
            }
            for r in size_rows
        ],
        "timeline": [
            {
                "kind": e.kind,
                "at": e.at,
                "number": e.number,
                "amount_usd": e.amount_usd,
                "note": e.note,
                "order_id": e.order_id,
                "lines": e.lines,
            }
            for e in events[:limit]
        ],
    }
