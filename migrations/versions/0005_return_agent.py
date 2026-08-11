"""Qaytarishni agentga bog'lash (hisobotlarda ayirish uchun).

Revision ID: 0005_return_agent
Revises: 0004_extra_roles
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0005_return_agent"
down_revision = "0004_extra_roles"
branch_labels = None
depends_on = None

#: Eski qaytarishlarni buyurtma yoki vrach orqali agentga bog'laymiz
BACKFILL = """
UPDATE returns
SET agent_id = COALESCE(
    (SELECT o.agent_id FROM orders o WHERE o.id = returns.order_id),
    (SELECT d.agent_id FROM doctors d WHERE d.id = returns.doctor_id)
)
WHERE agent_id IS NULL
"""


def _has_column(table: str, column: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column in {c["name"] for c in inspector.get_columns(table)}


def upgrade() -> None:
    # Toza bazada `0001_initial` ustunni modellardan yaratib bo'lgan bo'ladi
    if not _has_column("returns", "agent_id"):
        op.add_column("returns", sa.Column("agent_id", sa.Integer(), nullable=True))
        op.create_index(op.f("ix_returns_agent_id"), "returns", ["agent_id"])
        op.create_foreign_key(
            op.f("fk_returns_agent_id_users"),
            "returns",
            "users",
            ["agent_id"],
            ["id"],
            ondelete="SET NULL",
        )

    op.execute(sa.text(BACKFILL))


def downgrade() -> None:
    if _has_column("returns", "agent_id"):
        op.drop_column("returns", "agent_id")
