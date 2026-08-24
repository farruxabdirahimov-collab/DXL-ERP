"""Menejer KPI: post va otziv videolari.

Menejer havolani tashlaydi, direktor tasdiqlaydi. Faqat **tasdiqlangan**
ish haqqa kiradi — shuning uchun son o'z-o'zidan shishib ketmaydi.
"""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, str_enum


class SubmissionKind(str, enum.Enum):
    POST = "post"      # Menejer o'zi joylagan video/post
    REVIEW = "review"  # Shifokordan olingan otziv videosi


class SubmissionStatus(str, enum.Enum):
    PENDING = "pending"    # Direktor tasdig'ini kutmoqda
    APPROVED = "approved"  # Hisobga olindi
    REJECTED = "rejected"  # Rad etildi


SUBMISSION_KIND_UZ: dict[SubmissionKind, str] = {
    SubmissionKind.POST: "Post / video",
    SubmissionKind.REVIEW: "Shifokor otzivi",
}

SUBMISSION_STATUS_UZ: dict[SubmissionStatus, str] = {
    SubmissionStatus.PENDING: "Tasdiq kutmoqda",
    SubmissionStatus.APPROVED: "Hisobga olindi",
    SubmissionStatus.REJECTED: "Rad etildi",
}


class ContentSubmission(Base, TimestampMixin):
    __tablename__ = "content_submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agent_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[SubmissionKind] = mapped_column(
        str_enum(SubmissionKind, "submission_kind_enum"), nullable=False, index=True
    )
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)

    status: Mapped[SubmissionStatus] = mapped_column(
        str_enum(SubmissionStatus, "submission_status_enum"),
        default=SubmissionStatus.PENDING,
        nullable=False,
        index=True,
    )
    #: Qaysi oyga hisoblanadi — tasdiqlangan sana emas, joylangan sana
    period_year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    period_month: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    reviewed_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reject_reason: Mapped[str | None] = mapped_column(Text)
