"""Taklif-shartnoma va tariflar.

Tarif — direktor tuzadigan taklif shabloni (paket, muddat, sovg'a).
Shartnoma — shu taklif bo'yicha vrach bilan tuzilgan kelishuv.

Asosiy g'oya: sovg'a chegirma emas, **tez to'lov uchun rag'bat**. Vrach
muddat ichida to'liq to'lasa sovg'ani oladi; kechiksa yoki tovar qaytarsa —
sovg'a bekor bo'ladi, narx esa o'zgarmaydi.
"""

from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, str_enum


class ContractStatus(str, enum.Enum):
    ACTIVE = "active"        # amalda, sanoq ketyapti
    PAID = "paid"            # to'liq to'langan
    OVERDUE = "overdue"      # muddat o'tdi, qarz qoldi
    CANCELLED = "cancelled"  # bekor qilingan


class GiftStatus(str, enum.Enum):
    PENDING = "pending"  # sanoq ketyapti, hali qozonilmagan
    EARNED = "earned"    # muddatida to'langan — sovg'a qozonildi
    ISSUED = "issued"    # sovg'a jismonan berildi
    LOST = "lost"        # muddat o'tdi yoki tovar qaytarildi


CONTRACT_STATUS_UZ: dict[ContractStatus, str] = {
    ContractStatus.ACTIVE: "Amalda",
    ContractStatus.PAID: "To'liq to'langan",
    ContractStatus.OVERDUE: "Muddati o'tgan",
    ContractStatus.CANCELLED: "Bekor qilingan",
}

GIFT_STATUS_UZ: dict[GiftStatus, str] = {
    GiftStatus.PENDING: "Kutilmoqda",
    GiftStatus.EARNED: "Qozonildi",
    GiftStatus.ISSUED: "Berildi",
    GiftStatus.LOST: "Yo'qotildi",
}


class Tariff(Base, TimestampMixin):
    """Direktor tuzadigan taklif shabloni."""

    __tablename__ = "tariffs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    #: Vrach ko'radigan nom — "Katta-100"
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    #: Paketdagi implant soni
    package_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    #: Paketning qat'iy narxi — qaysi razmer tanlanishidan qat'i nazar
    package_price_usd: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    #: To'liq to'lov muddati (kun)
    term_days: Mapped[int] = mapped_column(Integer, nullable=False)
    #: Sovg'a nomi — vrach shuni ko'radi
    gift_name: Mapped[str | None] = mapped_column(String(120))
    #: Sovg'aning bizga tushadigan tannarxi — vrach ko'rmaydi, foyda uchun
    gift_cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0"), nullable=False
    )
    #: Sovg'a katalogdagi mahsulot bo'lsa — ombordan chiqadi
    gift_product_id: Mapped[int | None] = mapped_column(
        ForeignKey("products.id", ondelete="SET NULL")
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    note: Mapped[str | None] = mapped_column(Text)

    @property
    def unit_price_usd(self) -> Decimal:
        if not self.package_qty:
            return Decimal("0")
        return Decimal(self.package_price_usd) / self.package_qty

    @property
    def gift_share_pct(self) -> Decimal:
        """Sovg'aning paket summasidagi ulushi — zinapoyani tekshirish uchun."""
        if not self.package_price_usd:
            return Decimal("0")
        return Decimal(self.gift_cost_usd) / Decimal(self.package_price_usd) * 100


class Contract(Base, TimestampMixin):
    """Vrach bilan tuzilgan taklif-shartnoma va uning teskari sanog'i."""

    __tablename__ = "contracts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    number: Mapped[str] = mapped_column(String(24), unique=True, nullable=False)
    doctor_id: Mapped[int] = mapped_column(
        ForeignKey("doctors.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    tariff_id: Mapped[int | None] = mapped_column(
        ForeignKey("tariffs.id", ondelete="SET NULL"), index=True
    )
    agent_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )

    # --- Tarif shartlari NUSXASI ---------------------------------------
    # Tarif keyin o'zgarsa yoki o'chsa, tuzilgan shartnoma o'z shartlarida
    # qoladi — xuddi narx hujjatda qotib qolgani kabi.
    tariff_name: Mapped[str] = mapped_column(String(80), nullable=False)
    package_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    package_price_usd: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    term_days: Mapped[int] = mapped_column(Integer, nullable=False)
    gift_name: Mapped[str | None] = mapped_column(String(120))
    gift_cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0"), nullable=False
    )

    # --- Teskari sanoq -------------------------------------------------
    #: Sanoq boshlanishi — shartnoma imzolangan aniq vaqt
    signed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    #: signed_at + term_days — teskari sanoq shu vaqtga qarab yuradi
    deadline_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    # --- Bajarilishi ---------------------------------------------------
    #: Paketdan nechta dona haqiqatan yetkazildi
    delivered_qty: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    paid_usd: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0"), nullable=False
    )
    #: Haqiqiy tannarx — yetkazilgan tovarning o'sha paytdagi tannarxi
    cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0"), nullable=False
    )
    #: Qaytarilgan summa — bo'lsa sovg'a bekor bo'ladi
    returned_usd: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0"), nullable=False
    )

    status: Mapped[ContractStatus] = mapped_column(
        str_enum(ContractStatus, "contract_status_enum"),
        default=ContractStatus.ACTIVE,
        nullable=False,
        index=True,
    )
    gift_status: Mapped[GiftStatus] = mapped_column(
        str_enum(GiftStatus, "gift_status_enum"),
        default=GiftStatus.PENDING,
        nullable=False,
        index=True,
    )
    gift_issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    gift_issued_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    #: Sovg'a qozonilgan yoki yo'qotilgan payt — sabab bilan
    gift_note: Mapped[str | None] = mapped_column(Text)
    #: Tabrik xabari yuborilganmi — takror ketmasin
    gift_notified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    note: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    #: 7/3/1 kunlik eslatmalardan qaysilari yuborilgani — takror ketmasin
    reminders_sent: Mapped[str | None] = mapped_column(String(32))

    doctor: Mapped["Doctor"] = relationship()  # type: ignore[name-defined]  # noqa: F821

    @property
    def remaining_usd(self) -> Decimal:
        """Sovg'ani olish uchun yana qancha to'lash kerak."""
        qoldi = Decimal(self.package_price_usd) - Decimal(self.paid_usd)
        return qoldi if qoldi > 0 else Decimal("0")

    @property
    def paid_pct(self) -> float:
        if not self.package_price_usd:
            return 0.0
        return float(Decimal(self.paid_usd) / Decimal(self.package_price_usd) * 100)

    @property
    def is_open(self) -> bool:
        return self.status is ContractStatus.ACTIVE
