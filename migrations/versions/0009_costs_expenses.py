"""Tannarx maydonlari va xarajatlar — foyda-zarar hisoboti uchun.

Revision ID: 0009_costs_expenses
Revises: 0008_company_plan
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0009_costs_expenses"
down_revision = "0008_company_plan"
branch_labels = None
depends_on = None

#: Tannarx qo'shiladigan jadvallar
COST_TABLES = ("products", "order_items", "return_items", "writeoff_items")


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _has_column(table: str, column: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column in {c["name"] for c in inspector.get_columns(table)}


def upgrade() -> None:
    tables = _tables()

    for table in COST_TABLES:
        if table in tables and not _has_column(table, "cost_usd"):
            op.add_column(
                table,
                sa.Column(
                    "cost_usd", sa.Numeric(12, 2), nullable=False, server_default="0"
                ),
            )

    if "expenses" not in tables:
        op.create_table(
            "expenses",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("category", sa.String(32), nullable=False),
            sa.Column("spent_on", sa.Date(), nullable=False),
            sa.Column("amount_usd", sa.Numeric(14, 2), nullable=False),
            sa.Column("is_monthly", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("ended_on", sa.Date()),
            sa.Column("note", sa.Text()),
            sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
            # TimestampMixin qiymatni bazadan kutadi (0006 dagi xato takrorlanmasin)
            sa.Column(
                "created_at", sa.DateTime(timezone=True),
                server_default=sa.text("now()"), nullable=False,
            ),
            sa.Column(
                "updated_at", sa.DateTime(timezone=True),
                server_default=sa.text("now()"), nullable=False,
            ),
        )
        for col in ("category", "spent_on", "is_monthly", "created_at"):
            op.create_index(f"ix_expenses_{col}", "expenses", [col])


def downgrade() -> None:
    if "expenses" in _tables():
        op.drop_table("expenses")
    for table in COST_TABLES:
        if _has_column(table, "cost_usd"):
            op.drop_column(table, "cost_usd")
