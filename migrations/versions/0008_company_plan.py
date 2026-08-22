"""Kompaniya oylik rejasi va agent rejasining yangi ko'rsatkichlari.

Revision ID: 0008_company_plan
Revises: 0007_contract_defaults
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0008_company_plan"
down_revision = "0007_contract_defaults"
branch_labels = None
depends_on = None

#: Agent rejasiga qo'shiladigan ixtiyoriy maqsadlar (0 = hisobga olinmaydi)
YANGI_USTUNLAR = ("target_new_doctors", "target_active_doctors", "target_visits")


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _has_column(table: str, column: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column in {c["name"] for c in inspector.get_columns(table)}


def upgrade() -> None:
    if "company_plans" not in _tables():
        op.create_table(
            "company_plans",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("year", sa.Integer(), nullable=False),
            sa.Column("month", sa.Integer(), nullable=False),
            sa.Column("target_amount_usd", sa.Numeric(14, 2), nullable=False, server_default="0"),
            sa.Column("target_units", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("target_collection_usd", sa.Numeric(14, 2), nullable=False, server_default="0"),
            sa.Column("target_new_doctors", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("note", sa.Text()),
            sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
            # TimestampMixin bazadan qiymat kutadi — default'siz qoldirilsa
            # INSERT paytida NULL tushib xato beradi (0006 dagi xato takrorlanmasin)
            sa.Column(
                "created_at", sa.DateTime(timezone=True),
                server_default=sa.text("now()"), nullable=False,
            ),
            sa.Column(
                "updated_at", sa.DateTime(timezone=True),
                server_default=sa.text("now()"), nullable=False,
            ),
            sa.UniqueConstraint("year", "month", name="company_plan_period"),
        )
        op.create_index("ix_company_plans_created_at", "company_plans", ["created_at"])

    if "sales_plans" in _tables():
        for column in YANGI_USTUNLAR:
            if not _has_column("sales_plans", column):
                op.add_column(
                    "sales_plans",
                    sa.Column(column, sa.Integer(), nullable=False, server_default="0"),
                )


def downgrade() -> None:
    for column in YANGI_USTUNLAR:
        if _has_column("sales_plans", column):
            op.drop_column("sales_plans", column)
    if "company_plans" in _tables():
        op.drop_table("company_plans")
