"""Menejer KPI: post va otziv havolalari (direktor tasdiqlaydi).

Revision ID: 0010_kpi
Revises: 0009_costs_expenses
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0010_kpi"
down_revision = "0009_costs_expenses"
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    if "content_submissions" in _tables():
        return

    op.create_table(
        "content_submissions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("agent_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("url", sa.String(500), nullable=False),
        sa.Column("note", sa.Text()),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("period_year", sa.Integer(), nullable=False),
        sa.Column("period_month", sa.Integer(), nullable=False),
        sa.Column("reviewed_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("reject_reason", sa.Text()),
        # TimestampMixin qiymatni bazadan kutadi
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
    )
    for col in ("agent_id", "kind", "status", "period_year", "period_month", "created_at"):
        op.create_index(f"ix_content_submissions_{col}", "content_submissions", [col])


def downgrade() -> None:
    if "content_submissions" in _tables():
        op.drop_table("content_submissions")
