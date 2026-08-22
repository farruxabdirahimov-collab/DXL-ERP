"""Xarajatlar — foyda-zarar hisoboti uchun.

Soddalik uchun ikki xil: bir martalik xarajat va har oy takrorlanadigan
(ijara, oylik). Takrorlanadigani bir marta kiritiladi va har oy hisobga
olinadi — har oy qayta yozish shart emas.
"""

from __future__ import annotations

import enum
from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, str_enum


class ExpenseCategory(str, enum.Enum):
    SALARY = "salary"        # Xodimlar oyligi
    RENT = "rent"            # Ijara
    TRANSPORT = "transport"  # Transport va yetkazib berish
    CUSTOMS = "customs"      # Bojxona va rasmiylashtirish
    MARKETING = "marketing"  # Reklama va marketing
    COMMS = "comms"          # Aloqa va internet
    BANK = "bank"            # Bank xizmati
    TAX = "tax"              # Soliq
    OTHER = "other"          # Boshqa


EXPENSE_LABELS_UZ: dict[ExpenseCategory, str] = {
    ExpenseCategory.SALARY: "Xodimlar oyligi",
    ExpenseCategory.RENT: "Ijara",
    ExpenseCategory.TRANSPORT: "Transport",
    ExpenseCategory.CUSTOMS: "Bojxona",
    ExpenseCategory.MARKETING: "Reklama",
    ExpenseCategory.COMMS: "Aloqa va internet",
    ExpenseCategory.BANK: "Bank xizmati",
    ExpenseCategory.TAX: "Soliq",
    ExpenseCategory.OTHER: "Boshqa",
}


class Expense(Base, TimestampMixin):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category: Mapped[ExpenseCategory] = mapped_column(
        str_enum(ExpenseCategory, "expense_category_enum"), nullable=False, index=True
    )
    #: Xarajat sanasi. Takrorlanadigan xarajatda — boshlanish sanasi.
    spent_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    amount_usd: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    #: Har oy takrorlanadimi (ijara, oylik). Bir marta kiritiladi.
    is_monthly: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, index=True
    )
    #: Takrorlanadigan xarajat qachon to'xtagan (bo'sh — hali amalda)
    ended_on: Mapped[date | None] = mapped_column(Date)

    note: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    def active_in(self, year: int, month: int) -> bool:
        """Shu oyda hisobga olinadimi."""
        boshlandi = (self.spent_on.year, self.spent_on.month) <= (year, month)
        if not self.is_monthly:
            return (self.spent_on.year, self.spent_on.month) == (year, month)
        if not boshlandi:
            return False
        if self.ended_on is None:
            return True
        return (year, month) <= (self.ended_on.year, self.ended_on.month)
