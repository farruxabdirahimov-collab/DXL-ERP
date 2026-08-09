"""Xodimga qo'shimcha rol berish imkoniyati.

Revision ID: 0004_extra_roles
Revises: 0003_content
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0004_extra_roles"
down_revision = "0003_content"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column in {c["name"] for c in inspector.get_columns(table)}


def upgrade() -> None:
    # Toza bazada `0001_initial` ustunlarni modellardan yaratib bo'lgan bo'ladi
    for table in ("users", "invites"):
        if not _has_column(table, "extra_roles"):
            op.add_column(
                table,
                sa.Column(
                    "extra_roles",
                    sa.JSON(),
                    nullable=False,
                    server_default=sa.text("'[]'"),
                ),
            )


def downgrade() -> None:
    for table in ("users", "invites"):
        if _has_column(table, "extra_roles"):
            op.drop_column(table, "extra_roles")
