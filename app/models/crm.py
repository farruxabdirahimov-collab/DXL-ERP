"""Vrachlar (mijozlar), tashriflar va agent vazifalari."""

from __future__ import annotations

import enum
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, BigIntPK, TimestampMixin, str_enum


class DoctorCategory(str, enum.Enum):
    """Xarid darajasi — oxirgi 12 oylik sotuv bo'yicha avtomatik hisoblanadi."""

    A = "A"  # Eng yirik mijozlar (yuqori 20%)
    B = "B"  # O'rta (keyingi 30%)
    C = "C"  # Kichik / yangi
    NEW = "new"  # Hali xarid qilmagan


CATEGORY_LABELS_UZ: dict[DoctorCategory, str] = {
    DoctorCategory.A: "A — yirik mijoz",
    DoctorCategory.B: "B — o'rta mijoz",
    DoctorCategory.C: "C — kichik mijoz",
    DoctorCategory.NEW: "Yangi",
}


class VisitResult(str, enum.Enum):
    ORDER = "order"          # Buyurtma olindi
    NO_ORDER = "no_order"    # Buyurtmasiz
    NOT_THERE = "not_there"  # Vrach joyida yo'q edi
    PAYMENT = "payment"      # Pul yig'ildi


class TaskKind(str, enum.Enum):
    BIRTHDAY = "birthday"    # Tug'ilgan kun tabrigi
    SLEEPING = "sleeping"    # Uzoq vaqt xarid qilmagan mijoz
    OVERDUE = "overdue"      # Muddati o'tgan qarz
    MANUAL = "manual"        # Qo'lda qo'yilgan vazifa


TASK_LABELS_UZ: dict[TaskKind, str] = {
    TaskKind.BIRTHDAY: "Tug'ilgan kun",
    TaskKind.SLEEPING: "Uzoq xarid qilmagan",
    TaskKind.OVERDUE: "Qarz muddati o'tgan",
    TaskKind.MANUAL: "Vazifa",
}


class TaskStatus(str, enum.Enum):
    OPEN = "open"
    DONE = "done"
    SKIPPED = "skipped"


class Doctor(Base, TimestampMixin):
    """Xaridor — vrach."""

    __tablename__ = "doctors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    phone: Mapped[str] = mapped_column(String(20), nullable=False, unique=True, index=True)
    extra_phone: Mapped[str | None] = mapped_column(String(20))
    clinic_name: Mapped[str | None] = mapped_column(String(200), index=True)

    # --- Manzil ---
    region: Mapped[str | None] = mapped_column(String(80), index=True)
    district: Mapped[str | None] = mapped_column(String(80))
    address: Mapped[str | None] = mapped_column(Text)
    lat: Mapped[float | None] = mapped_column(Float)
    lon: Mapped[float | None] = mapped_column(Float)

    birth_date: Mapped[date | None] = mapped_column(Date, index=True)
    specialty: Mapped[str | None] = mapped_column(String(120))

    #: Biriktirilgan sotuv agenti
    agent_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    #: Vrach o'zi Mini App'ga kirsa — Telegram hisobi
    telegram_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, index=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), unique=True
    )

    # --- Moliyaviy shartlar (har vrachga alohida) ---
    debt_limit_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0"), nullable=False
    )
    payment_term_days: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    discount_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("0"), nullable=False
    )

    # --- Avtomatik hisoblanadigan ko'rsatkichlar (har kecha yangilanadi) ---
    category: Mapped[DoctorCategory] = mapped_column(
        str_enum(DoctorCategory, "doctor_category_enum"),
        default=DoctorCategory.NEW,
        nullable=False,
        index=True,
    )
    loyalty_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False, index=True)
    total_purchased_usd: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0"), nullable=False
    )
    purchased_12m_usd: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0"), nullable=False
    )
    orders_12m: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    avg_payment_delay_days: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    last_order_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    metrics_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    #: Direktor qo'lda blokdan chiqarganda
    credit_block_override: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )


class Visit(Base):
    """Agentning vrach oldiga tashrifi (geolokatsiya bilan)."""

    __tablename__ = "visits"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    agent_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    doctor_id: Mapped[int] = mapped_column(
        ForeignKey("doctors.id", ondelete="CASCADE"), nullable=False, index=True
    )
    lat: Mapped[float | None] = mapped_column(Float)
    lon: Mapped[float | None] = mapped_column(Float)
    #: Klinika manzilidan masofa (metr) — soxta tashrifni aniqlash uchun
    distance_m: Mapped[float | None] = mapped_column(Float)
    result: Mapped[VisitResult | None] = mapped_column(
        str_enum(VisitResult, "visit_result_enum")
    )
    order_id: Mapped[int | None] = mapped_column(
        ForeignKey("orders.id", ondelete="SET NULL")
    )
    note: Mapped[str | None] = mapped_column(Text)


class Task(Base):
    """Agentga tushadigan vazifa/eslatma."""

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    doctor_id: Mapped[int | None] = mapped_column(
        ForeignKey("doctors.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[TaskKind] = mapped_column(
        str_enum(TaskKind, "task_kind_enum"), nullable=False, index=True
    )
    due_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[TaskStatus] = mapped_column(
        str_enum(TaskStatus, "task_status_enum"),
        default=TaskStatus.OPEN,
        nullable=False,
        index=True,
    )
    #: Takror yaratilmasligi uchun kalit, masalan "birthday:12:2026-08-08"
    dedup_key: Mapped[str | None] = mapped_column(String(120), unique=True, index=True)
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    note: Mapped[str | None] = mapped_column(Text)
