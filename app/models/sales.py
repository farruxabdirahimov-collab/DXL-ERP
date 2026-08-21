"""Buyurtma/sotuv, qaytarish, spisaniye, kirim va ko'chirish hujjatlari."""

from __future__ import annotations

import enum
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, str_enum


class OrderStatus(str, enum.Enum):
    NEW = "new"                          # Yaratildi, agent tasdig'ini kutmoqda
    DIRECTOR_REVIEW = "director_review"  # Direktor tasdig'i kerak (chegirma/qarz)
    APPROVED = "approved"                # Tasdiqlandi, tovar band qilindi
    PICKING = "picking"                  # Omborchi yig'moqda
    SHIPPED = "shipped"                  # Yo'lda
    DELIVERED = "delivered"              # Yetkazildi — sotuv amalga oshdi
    CANCELLED = "cancelled"              # Bekor qilindi
    REJECTED = "rejected"                # Rad etildi


STATUS_LABELS_UZ: dict[OrderStatus, str] = {
    OrderStatus.NEW: "Yangi — tasdiq kutilmoqda",
    OrderStatus.DIRECTOR_REVIEW: "Direktor tasdig'i kerak",
    OrderStatus.APPROVED: "Tasdiqlandi",
    OrderStatus.PICKING: "Yig'ilmoqda",
    OrderStatus.SHIPPED: "Yo'lda",
    OrderStatus.DELIVERED: "Yetkazildi",
    OrderStatus.CANCELLED: "Bekor qilindi",
    OrderStatus.REJECTED: "Rad etildi",
}

#: Tovar band qilingan (rezerv) holatlar
RESERVED_STATUSES = (OrderStatus.APPROVED, OrderStatus.PICKING, OrderStatus.SHIPPED)
#: Yopilmagan (jarayondagi) holatlar
OPEN_STATUSES = (
    OrderStatus.NEW,
    OrderStatus.DIRECTOR_REVIEW,
    OrderStatus.APPROVED,
    OrderStatus.PICKING,
    OrderStatus.SHIPPED,
)


class OrderSource(str, enum.Enum):
    DOCTOR = "doctor"  # Vrach o'zi Mini App orqali berdi
    AGENT = "agent"    # Agent kiritdi


class Order(Base, TimestampMixin):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    number: Mapped[str] = mapped_column(String(24), unique=True, index=True, nullable=False)

    doctor_id: Mapped[int] = mapped_column(
        ForeignKey("doctors.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    agent_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    #: Taklif-shartnoma hisobidan ketgan bo'lsa — paket narxi shundan olinadi
    contract_id: Mapped[int | None] = mapped_column(
        ForeignKey("contracts.id", ondelete="SET NULL"), index=True
    )
    warehouse_id: Mapped[int] = mapped_column(
        ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    source: Mapped[OrderSource] = mapped_column(
        str_enum(OrderSource, "order_source_enum"), nullable=False
    )
    status: Mapped[OrderStatus] = mapped_column(
        str_enum(OrderStatus, "order_status_enum"),
        default=OrderStatus.NEW,
        nullable=False,
        index=True,
    )

    # --- Summalar (USD) ---
    subtotal_usd: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0"), nullable=False
    )
    discount_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("0"), nullable=False
    )
    discount_usd: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0"), nullable=False
    )
    total_usd: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0"), nullable=False, index=True
    )
    #: Hujjat yaratilgandagi kurs — keyin o'zgarmaydi
    fx_rate: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    #: To'langan summa (USD ekvivalent), to'lov servisi yangilaydi
    paid_usd: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0"), nullable=False
    )
    #: Qaytarilgan summa (USD)
    returned_usd: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0"), nullable=False
    )
    due_date: Mapped[date | None] = mapped_column(Date, index=True)

    #: Chegirma limitidan oshgani yoki qarz limiti sabab direktor ko'rigi kerak
    needs_director: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    director_reason: Mapped[str | None] = mapped_column(String(200))

    comment: Mapped[str | None] = mapped_column(Text)
    cancel_reason: Mapped[str | None] = mapped_column(Text)

    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    approved_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan", lazy="selectin"
    )

    @property
    def debt_usd(self) -> Decimal:
        """Shu buyurtma bo'yicha qolgan qarz."""
        return self.total_usd - self.paid_usd - self.returned_usd

    @property
    def total_qty(self) -> int:
        return sum(item.qty for item in self.items)


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    price_usd: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    discount_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("0"), nullable=False
    )
    line_total_usd: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    order: Mapped[Order] = relationship(back_populates="items")

    __table_args__ = (UniqueConstraint("order_id", "product_id", name="order_product"),)


class Return(Base, TimestampMixin):
    """Vrachdan tovar qaytarish."""

    __tablename__ = "returns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    number: Mapped[str] = mapped_column(String(24), unique=True, nullable=False)
    doctor_id: Mapped[int] = mapped_column(
        ForeignKey("doctors.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    order_id: Mapped[int | None] = mapped_column(
        ForeignKey("orders.id", ondelete="SET NULL"), index=True
    )
    warehouse_id: Mapped[int] = mapped_column(
        ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False
    )
    #: Qaysi agent hisobidan ayiriladi (sotuv va reja hisobotlari uchun)
    agent_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    total_usd: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0"), nullable=False
    )
    reason: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    items: Mapped[list["ReturnItem"]] = relationship(
        back_populates="parent", cascade="all, delete-orphan", lazy="selectin"
    )


class ReturnItem(Base):
    __tablename__ = "return_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    return_id: Mapped[int] = mapped_column(
        ForeignKey("returns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    price_usd: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    line_total_usd: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    parent: Mapped[Return] = relationship(back_populates="items")

    __table_args__ = (UniqueConstraint("return_id", "product_id", name="return_product"),)


class WriteOff(Base, TimestampMixin):
    """Spisaniye — yaroqsiz/singan/yo'qolgan tovar."""

    __tablename__ = "writeoffs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    number: Mapped[str] = mapped_column(String(24), unique=True, nullable=False)
    warehouse_id: Mapped[int] = mapped_column(
        ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    total_usd: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0"), nullable=False
    )
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    items: Mapped[list["WriteOffItem"]] = relationship(
        back_populates="parent", cascade="all, delete-orphan", lazy="selectin"
    )


class WriteOffItem(Base):
    __tablename__ = "writeoff_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    writeoff_id: Mapped[int] = mapped_column(
        ForeignKey("writeoffs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    price_usd: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    parent: Mapped[WriteOff] = relationship(back_populates="items")

    __table_args__ = (
        UniqueConstraint("writeoff_id", "product_id", name="writeoff_product"),
    )


class Receipt(Base, TimestampMixin):
    """Yetkazib beruvchidan kirim."""

    __tablename__ = "receipts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    number: Mapped[str] = mapped_column(String(24), unique=True, nullable=False)
    warehouse_id: Mapped[int] = mapped_column(
        ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    supplier: Mapped[str | None] = mapped_column(String(160))
    invoice_no: Mapped[str | None] = mapped_column(String(64))
    total_usd: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0"), nullable=False
    )
    note: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    items: Mapped[list["ReceiptItem"]] = relationship(
        back_populates="parent", cascade="all, delete-orphan", lazy="selectin"
    )


class ReceiptItem(Base):
    __tablename__ = "receipt_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    receipt_id: Mapped[int] = mapped_column(
        ForeignKey("receipts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0"), nullable=False
    )

    parent: Mapped[Receipt] = relationship(back_populates="items")

    __table_args__ = (UniqueConstraint("receipt_id", "product_id", name="receipt_product"),)


class Transfer(Base, TimestampMixin):
    """Omborlar orasida ko'chirish (markaziy ombor -> agent ombori)."""

    __tablename__ = "transfers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    number: Mapped[str] = mapped_column(String(24), unique=True, nullable=False)
    from_warehouse_id: Mapped[int] = mapped_column(
        ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    to_warehouse_id: Mapped[int] = mapped_column(
        ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    note: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    items: Mapped[list["TransferItem"]] = relationship(
        back_populates="parent", cascade="all, delete-orphan", lazy="selectin"
    )


class TransferItem(Base):
    __tablename__ = "transfer_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    transfer_id: Mapped[int] = mapped_column(
        ForeignKey("transfers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    qty: Mapped[int] = mapped_column(Integer, nullable=False)

    parent: Mapped[Transfer] = relationship(back_populates="items")

    __table_args__ = (
        UniqueConstraint("transfer_id", "product_id", name="transfer_product"),
    )
