"""Tariflar va taklif-shartnomalar (teskari sanoq bilan).

Revision ID: 0006_contracts
Revises: 0005_return_agent
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006_contracts"
down_revision = "0005_return_agent"
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _has_column(table: str, column: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column in {c["name"] for c in inspector.get_columns(table)}


def upgrade() -> None:
    # Toza bazada `0001_initial` jadvallarni modellardan yaratib bo'lgan bo'ladi
    tables = _tables()

    if "tariffs" not in tables:
        op.create_table(
            "tariffs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(80), nullable=False, unique=True),
            sa.Column("package_qty", sa.Integer(), nullable=False),
            sa.Column("package_price_usd", sa.Numeric(14, 2), nullable=False),
            sa.Column("term_days", sa.Integer(), nullable=False),
            sa.Column("gift_name", sa.String(120)),
            sa.Column("gift_cost_usd", sa.Numeric(12, 2), nullable=False, server_default="0"),
            sa.Column("gift_product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="SET NULL")),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="100"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("note", sa.Text()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )

    if "contracts" not in tables:
        op.create_table(
            "contracts",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("number", sa.String(24), nullable=False, unique=True),
            sa.Column("doctor_id", sa.Integer(), sa.ForeignKey("doctors.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("tariff_id", sa.Integer(), sa.ForeignKey("tariffs.id", ondelete="SET NULL")),
            sa.Column("agent_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
            sa.Column("tariff_name", sa.String(80), nullable=False),
            sa.Column("package_qty", sa.Integer(), nullable=False),
            sa.Column("package_price_usd", sa.Numeric(14, 2), nullable=False),
            sa.Column("term_days", sa.Integer(), nullable=False),
            sa.Column("gift_name", sa.String(120)),
            sa.Column("gift_cost_usd", sa.Numeric(12, 2), nullable=False, server_default="0"),
            sa.Column("signed_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("delivered_qty", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("paid_usd", sa.Numeric(14, 2), nullable=False, server_default="0"),
            sa.Column("cost_usd", sa.Numeric(14, 2), nullable=False, server_default="0"),
            sa.Column("returned_usd", sa.Numeric(14, 2), nullable=False, server_default="0"),
            sa.Column("status", sa.String(16), nullable=False, server_default="active"),
            sa.Column("gift_status", sa.String(16), nullable=False, server_default="pending"),
            sa.Column("gift_issued_at", sa.DateTime(timezone=True)),
            sa.Column("gift_issued_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
            sa.Column("gift_note", sa.Text()),
            sa.Column("gift_notified", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("closed_at", sa.DateTime(timezone=True)),
            sa.Column("note", sa.Text()),
            sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
            sa.Column("reminders_sent", sa.String(32)),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        for col in ("doctor_id", "tariff_id", "agent_id", "signed_at", "deadline_at", "status", "gift_status"):
            op.create_index(f"ix_contracts_{col}", "contracts", [col])

    # Buyurtma qaysi shartnoma hisobidan ketganini bog'laymiz
    if "orders" in tables and not _has_column("orders", "contract_id"):
        op.add_column("orders", sa.Column("contract_id", sa.Integer(), nullable=True))
        op.create_index("ix_orders_contract_id", "orders", ["contract_id"])
        op.create_foreign_key(
            "fk_orders_contract_id_contracts", "orders", "contracts",
            ["contract_id"], ["id"], ondelete="SET NULL",
        )


def downgrade() -> None:
    if _has_column("orders", "contract_id"):
        op.drop_column("orders", "contract_id")
    for table in ("contracts", "tariffs"):
        if table in _tables():
            op.drop_table(table)
