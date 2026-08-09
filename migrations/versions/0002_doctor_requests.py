"""Vrachning o'zi yuboradigan ro'yxatdan o'tish arizasi.

Revision ID: 0002_doctor_requests
Revises: 0001_initial
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0002_doctor_requests"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # `0001_initial` sxemani modellardan yaratadi, shuning uchun TOZA bazada bu
    # jadval allaqachon mavjud bo'ladi. Mavjud bazada esa yo'q — ikkala holat ham
    # to'g'ri ishlashi uchun avval tekshiramiz.
    inspector = sa.inspect(op.get_bind())
    if "doctor_requests" in inspector.get_table_names():
        return

    op.create_table(
        "doctor_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("telegram_username", sa.String(length=64), nullable=True),
        sa.Column("full_name", sa.String(length=160), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("clinic_name", sa.String(length=200), nullable=True),
        sa.Column("region", sa.String(length=80), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "pending", "approved", "rejected",
                name="request_status_enum", native_enum=False, length=32,
            ),
            nullable=False,
        ),
        sa.Column("reviewed_by_id", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reject_reason", sa.Text(), nullable=True),
        sa.Column("doctor_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["doctor_id"], ["doctors.id"],
            name=op.f("fk_doctor_requests_doctor_id_doctors"), ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by_id"], ["users.id"],
            name=op.f("fk_doctor_requests_reviewed_by_id_users"), ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_doctor_requests")),
    )
    op.create_index(
        op.f("ix_doctor_requests_created_at"), "doctor_requests", ["created_at"]
    )
    op.create_index(op.f("ix_doctor_requests_phone"), "doctor_requests", ["phone"])
    op.create_index(op.f("ix_doctor_requests_status"), "doctor_requests", ["status"])
    op.create_index(
        op.f("ix_doctor_requests_telegram_id"),
        "doctor_requests",
        ["telegram_id"],
        unique=True,
    )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "doctor_requests" not in inspector.get_table_names():
        return
    op.drop_index(op.f("ix_doctor_requests_telegram_id"), table_name="doctor_requests")
    op.drop_index(op.f("ix_doctor_requests_status"), table_name="doctor_requests")
    op.drop_index(op.f("ix_doctor_requests_phone"), table_name="doctor_requests")
    op.drop_index(op.f("ix_doctor_requests_created_at"), table_name="doctor_requests")
    op.drop_table("doctor_requests")
