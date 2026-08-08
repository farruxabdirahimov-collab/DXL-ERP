"""Umumiy model bazasi va yordamchi tiplar."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum as SAEnum,
    Integer,
    MetaData,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

#: Katta jadvallar uchun BIGINT birlamchi kalit.
#: SQLite'da AUTOINCREMENT faqat INTEGER uchun ishlaydi — shuning uchun variant.
BigIntPK = BigInteger().with_variant(Integer, "sqlite")

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def str_enum(enum_cls, name: str) -> SAEnum:
    """Enum'ni VARCHAR + CHECK sifatida saqlaymiz (SQLite va Postgres'da bir xil)."""
    return SAEnum(
        enum_cls,
        name=name,
        native_enum=False,
        values_callable=lambda e: [item.value for item in e],
        length=32,
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=utcnow,
        nullable=False,
    )
