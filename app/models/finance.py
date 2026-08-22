"""To'lovlar, valyuta kursi, oylik rejalar va hujjat raqamlagichi."""

from __future__ import annotations

import enum
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
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

from app.models.base import Base, BigIntPK, TimestampMixin, str_enum


class PaymentMethod(str, enum.Enum):
    CASH = "cash"        # Naqd
    CARD = "card"        # Plastik karta
    TRANSFER = "transfer"  # Bank o'tkazmasi


METHOD_LABELS_UZ: dict[PaymentMethod, str] = {
    PaymentMethod.CASH: "Naqd",
    PaymentMethod.CARD: "Karta",
    PaymentMethod.TRANSFER: "O'tkazma",
}


class Payment(Base, TimestampMixin):
    """Vrachdan tushgan to'lov. Kirim so'mda, qarz USD'da yopiladi."""

    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    doctor_id: Mapped[int] = mapped_column(
        ForeignKey("doctors.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    #: Aniq buyurtmaga bog'langan bo'lsa. Bo'sh bo'lsa — eng eski qarzdan yopiladi.
    order_id: Mapped[int | None] = mapped_column(
        ForeignKey("orders.id", ondelete="SET NULL"), index=True
    )
    amount_uzs: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    fx_rate: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    amount_usd: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, index=True)
    method: Mapped[PaymentMethod] = mapped_column(
        str_enum(PaymentMethod, "payment_method_enum"), nullable=False
    )
    paid_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    #: Pulni kim qabul qildi (agent naqd yig'gan bo'lishi ham mumkin)
    received_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    #: Qaysi agent hisobiga yozilsin (reja "yig'ilgan pul" ko'rsatkichi uchun)
    agent_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    note: Mapped[str | None] = mapped_column(Text)

    allocations: Mapped[list["PaymentAllocation"]] = relationship(
        back_populates="payment", cascade="all, delete-orphan", lazy="selectin"
    )


class PaymentAllocation(Base):
    """To'lovning qaysi buyurtmaga qancha yopilgani."""

    __tablename__ = "payment_allocations"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    payment_id: Mapped[int] = mapped_column(
        ForeignKey("payments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    amount_usd: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    payment: Mapped[Payment] = relationship(back_populates="allocations")

    __table_args__ = (UniqueConstraint("payment_id", "order_id", name="payment_order"),)


class FxRate(Base):
    """Kunlik USD/UZS kursi. Buxgalter yoki direktor kiritadi."""

    __tablename__ = "fx_rates"

    rate_date: Mapped[date] = mapped_column(Date, primary_key=True)
    usd_uzs: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    set_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SalesPlan(Base, TimestampMixin):
    """Agentning oylik rejasi — 3 ko'rsatkich bo'yicha."""

    __tablename__ = "sales_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)

    #: 1) Sotuv summasi (USD)
    target_amount_usd: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0"), nullable=False
    )
    #: 2) Sotilgan dona
    target_units: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    #: 4) Oyda nechta yangi vrach ochilsin (ixtiyoriy, 0 = hisobga olinmaydi)
    target_new_doctors: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    #: 5) Oyda kamida bir marta buyurtma bergan vrachlar soni
    target_active_doctors: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    #: 6) Geolokatsiyali tashriflar soni
    target_visits: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    #: 3) Vrachlardan yig'ilgan pul (USD)
    target_collection_usd: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0"), nullable=False
    )

    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    __table_args__ = (UniqueConstraint("user_id", "year", "month", name="plan_period"),)


class DocCounter(Base):
    """Hujjat raqamlarini ketma-ket berish uchun (masalan BUY-2026-00042)."""

    __tablename__ = "doc_counters"

    prefix: Mapped[str] = mapped_column(String(16), primary_key=True)
    year: Mapped[int] = mapped_column(Integer, primary_key=True)
    last_number: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class CompanyPlan(Base, TimestampMixin):
    """Kompaniyaning oylik maqsadi — direktor uchun.

    Agentlar rejalarining yig'indisi bundan kam bo'lsa, farq «egasiz reja»
    bo'lib qoladi: kimdir bajarishi kerak, lekin hech kimga biriktirilmagan.
    """

    __tablename__ = "company_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)

    target_amount_usd: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0"), nullable=False
    )
    target_units: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    target_collection_usd: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0"), nullable=False
    )
    target_new_doctors: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    note: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    __table_args__ = (UniqueConstraint("year", "month", name="company_plan_period"),)
