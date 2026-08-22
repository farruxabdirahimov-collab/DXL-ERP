"""Mahsulot katalogi, omborlar va qoldiq harakati."""

from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, BigIntPK, TimestampMixin, str_enum


class WarehouseKind(str, enum.Enum):
    MAIN = "main"      # Markaziy ombor
    AGENT = "agent"    # Agentning qo'l ombori


class MoveKind(str, enum.Enum):
    IN = "in"              # Kirim (yetkazib beruvchidan)
    TRANSFER = "transfer"  # Omborlar orasida ko'chirish
    SALE = "sale"          # Sotuv (chiqim)
    RETURN = "return"      # Vrachdan qaytarish (kirim)
    WRITEOFF = "writeoff"  # Spisaniye (chiqim)
    GIFT = "gift"          # Shartnoma sovg'asi (chiqim) — sotuv emas
    ADJUST = "adjust"      # Inventarizatsiya korreksiyasi


MOVE_LABELS_UZ: dict[MoveKind, str] = {
    MoveKind.IN: "Kirim",
    MoveKind.TRANSFER: "Ko'chirish",
    MoveKind.SALE: "Sotuv",
    MoveKind.GIFT: "Sovg'a",
    MoveKind.RETURN: "Qaytarish",
    MoveKind.WRITEOFF: "Spisaniye",
    MoveKind.ADJUST: "Korreksiya",
}


class ProductCategory(Base, TimestampMixin):
    __tablename__ = "product_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name_uz: Mapped[str] = mapped_column(String(120), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    products: Mapped[list["Product"]] = relationship(back_populates="category")


class Product(Base, TimestampMixin):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sku: Mapped[str] = mapped_column(String(48), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("product_categories.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    brand: Mapped[str] = mapped_column(String(48), default="DXL", nullable=False)

    #: Implant o'lchamlari — tahlilning asosiy kesimi
    diameter_mm: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    length_mm: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    #: Implant turi (masalan "Bone level", "Tissue level", "Konus")
    implant_type: Mapped[str | None] = mapped_column(String(64), index=True)
    #: Ulanish turi (masalan "Internal hex", "Conical")
    connection_type: Mapped[str | None] = mapped_column(String(64))

    unit: Mapped[str] = mapped_column(String(16), default="dona", nullable=False)
    price_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0"), nullable=False
    )
    min_stock: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(400))
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    category: Mapped[ProductCategory] = relationship(back_populates="products")

    __table_args__ = (
        CheckConstraint("price_usd >= 0", name="price_non_negative"),
        CheckConstraint("min_stock >= 0", name="min_stock_non_negative"),
        Index("ix_products_size", "diameter_mm", "length_mm"),
    )

    @property
    def size_label(self) -> str:
        """Masalan: "4.0 x 10.0 mm"."""
        if self.diameter_mm is None or self.length_mm is None:
            return "—"
        return f"{self.diameter_mm:g} x {self.length_mm:g} mm"


class Warehouse(Base, TimestampMixin):
    __tablename__ = "warehouses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    kind: Mapped[WarehouseKind] = mapped_column(
        str_enum(WarehouseKind, "warehouse_kind_enum"), nullable=False
    )
    #: Agent ombori bo'lsa — egasi
    owner_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), unique=True, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Stock(Base):
    """Kesh qoldiq. Yagona haqiqat manbai — `stock_moves`."""

    __tablename__ = "stock"

    warehouse_id: Mapped[int] = mapped_column(
        ForeignKey("warehouses.id", ondelete="CASCADE"), primary_key=True
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), primary_key=True
    )
    qty: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    #: Tasdiqlangan, lekin hali yetkazilmagan buyurtmalar uchun band qilingan miqdor
    reserved_qty: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("qty >= 0", name="qty_non_negative"),
        CheckConstraint("reserved_qty >= 0", name="reserved_non_negative"),
    )

    @property
    def available(self) -> int:
        return self.qty - self.reserved_qty


class StockMove(Base):
    """Har bir qoldiq o'zgarishi shu yerda qayd etiladi."""

    __tablename__ = "stock_moves"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    kind: Mapped[MoveKind] = mapped_column(
        str_enum(MoveKind, "move_kind_enum"), nullable=False, index=True
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    from_warehouse_id: Mapped[int | None] = mapped_column(
        ForeignKey("warehouses.id", ondelete="RESTRICT"), index=True
    )
    to_warehouse_id: Mapped[int | None] = mapped_column(
        ForeignKey("warehouses.id", ondelete="RESTRICT"), index=True
    )
    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    #: Hujjat manbai: "order", "receipt", "return", "writeoff", "transfer", "adjust"
    doc_type: Mapped[str | None] = mapped_column(String(32), index=True)
    doc_id: Mapped[int | None] = mapped_column(Integer, index=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    note: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint("qty > 0", name="move_qty_positive"),
        UniqueConstraint("doc_type", "doc_id", "product_id", "kind", name="doc_product_kind"),
    )
