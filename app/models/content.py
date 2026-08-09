"""Ma'rifiy kontent (maqola, video) va rassilkalar."""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, BigIntPK, TimestampMixin, str_enum


class PostKind(str, enum.Enum):
    ARTICLE = "article"    # Maqola
    VIDEO = "video"        # Video dars
    NEWS = "news"          # Yangilik / e'lon


POST_LABELS_UZ: dict[PostKind, str] = {
    PostKind.ARTICLE: "Maqola",
    PostKind.VIDEO: "Video",
    PostKind.NEWS: "Yangilik",
}


class Post(Base, TimestampMixin):
    """Vrachlar uchun material: implantlar haqida maqola, video dars, yangilik."""

    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[PostKind] = mapped_column(
        str_enum(PostKind, "post_kind_enum"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str | None] = mapped_column(String(400))
    body: Mapped[str | None] = mapped_column(Text)
    #: YouTube yoki Telegram video havolasi
    media_url: Mapped[str | None] = mapped_column(String(500))
    image_url: Mapped[str | None] = mapped_column(String(500))

    is_published: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, index=True
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )
    views: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    author_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )


class Audience(str, enum.Enum):
    ALL_DOCTORS = "all_doctors"    # Barcha vrachlar
    MY_DOCTORS = "my_doctors"      # Agentning o'z vrachlari
    CATEGORY_A = "category_a"      # A toifa (yirik mijozlar)
    CATEGORY_B = "category_b"
    CATEGORY_C = "category_c"
    DEBTORS = "debtors"            # Qarzi borlar
    ONE_DOCTOR = "one_doctor"      # Bitta vrachga shaxsiy xabar
    STAFF = "staff"                # Xodimlar


AUDIENCE_LABELS_UZ: dict[Audience, str] = {
    Audience.ALL_DOCTORS: "Barcha vrachlar",
    Audience.MY_DOCTORS: "Mening vrachlarim",
    Audience.CATEGORY_A: "A toifa vrachlar",
    Audience.CATEGORY_B: "B toifa vrachlar",
    Audience.CATEGORY_C: "C toifa vrachlar",
    Audience.DEBTORS: "Qarzi borlar",
    Audience.ONE_DOCTOR: "Bitta vrachga",
    Audience.STAFF: "Xodimlar",
}


class Broadcast(Base, TimestampMixin):
    """Yuborilgan rassilka — kimga, nima va nechtasi yetib borgani."""

    __tablename__ = "broadcasts"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    audience: Mapped[Audience] = mapped_column(
        str_enum(Audience, "audience_enum"), nullable=False
    )
    #: `ONE_DOCTOR` bo'lsa — kimga
    doctor_id: Mapped[int | None] = mapped_column(
        ForeignKey("doctors.id", ondelete="SET NULL")
    )
    #: Xabarga material biriktirilgan bo'lsa
    post_id: Mapped[int | None] = mapped_column(
        ForeignKey("posts.id", ondelete="SET NULL")
    )
    sent_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
