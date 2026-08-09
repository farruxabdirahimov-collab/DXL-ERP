"""Foydalanuvchilar, rollar, taklifnomalar, audit va sozlamalar."""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, BigIntPK, TimestampMixin, str_enum


class Role(str, enum.Enum):
    SUPERADMIN = "superadmin"      # Super-admin / IT
    DIRECTOR = "director"          # Direktor — rahbar
    FOUNDER = "founder"            # Ta'sischi — faqat ko'rish
    ACCOUNTANT = "accountant"      # Buxgalter / moliyachi
    WAREHOUSE = "warehouse"        # Omborxonachi
    AGENT = "agent"                # Sotuvchi agent
    DOCTOR = "doctor"              # Vrach — mijoz


ROLE_LABELS_UZ: dict[Role, str] = {
    Role.SUPERADMIN: "Super-admin",
    Role.DIRECTOR: "Direktor",
    Role.FOUNDER: "Ta'sischi",
    Role.ACCOUNTANT: "Buxgalter",
    Role.WAREHOUSE: "Omborchi",
    Role.AGENT: "Sotuv agenti",
    Role.DOCTOR: "Vrach",
}

#: Hisobotlarni to'liq ko'ra oladigan rahbariyat
MANAGEMENT_ROLES = (Role.SUPERADMIN, Role.DIRECTOR, Role.FOUNDER)
#: Ma'lumot o'zgartira oladigan rahbariyat (ta'sischi read-only)
ADMIN_ROLES = (Role.SUPERADMIN, Role.DIRECTOR)
#: Ichki xodimlar (vrachdan farqli)
STAFF_ROLES = (
    Role.SUPERADMIN,
    Role.DIRECTOR,
    Role.FOUNDER,
    Role.ACCOUNTANT,
    Role.WAREHOUSE,
    Role.AGENT,
)


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int | None] = mapped_column(
        BigInteger, unique=True, index=True, nullable=True
    )
    telegram_username: Mapped[str | None] = mapped_column(String(64))
    phone: Mapped[str | None] = mapped_column(String(20), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    role: Mapped[Role] = mapped_column(str_enum(Role, "role_enum"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    #: Agent uchun: o'zining qo'l ombori bo'ladimi (sozlanadigan)
    has_own_stock: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    #: Qo'shimcha rollar — bitta xodim bir vaqtda bir necha ish qilsa.
    #: Masalan asosiy rol "agent", qo'shimcha ["warehouse"] — u ham sotadi,
    #: ham omborni yuritadi. Ruxsatlar birlashtiriladi.
    extra_roles: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    note: Mapped[str | None] = mapped_column(Text)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    def __repr__(self) -> str:  # pragma: no cover - debug uchun
        return f"<User {self.id} {self.full_name} ({self.role.value})>"


class Invite(Base, TimestampMixin):
    """Xodimni tizimga taklif qilish uchun bir martalik havola."""

    __tablename__ = "invites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    role: Mapped[Role] = mapped_column(str_enum(Role, "invite_role_enum"), nullable=False)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20))
    has_own_stock: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    extra_roles: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    used_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditLog(Base):
    """O'zgarishlar jurnali — o'chirib bo'lmaydi."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    user_name: Mapped[str | None] = mapped_column(String(160))
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    entity_id: Mapped[str | None] = mapped_column(String(48))
    old_value: Mapped[dict | None] = mapped_column(JSON)
    new_value: Mapped[dict | None] = mapped_column(JSON)
    comment: Mapped[str | None] = mapped_column(Text)


class Setting(Base, TimestampMixin):
    """Tizim sozlamalari — kalit/qiymat."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON, nullable=False)
    label_uz: Mapped[str] = mapped_column(String(200), nullable=False, default="")


class Notification(Base):
    """Yuborilgan bildirishnomalar tarixi (takror yubormaslik uchun ham)."""

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    dedup_key: Mapped[str | None] = mapped_column(String(120), index=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    delivered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
