"""Qarz limitidan oshgan buyurtma to'xtamaydi, faqat belgilanadi.

Direktor tasdig'i real holatda hech qachon rad etilmagan — ya'ni u nazorat
emas, kechikish edi. Endi buyurtma o'tadi va sabab yozib qo'yiladi;
direktor «Nazorat» ro'yxatida keyin ko'radi.

Revision ID: 0011_over_limit
Revises: 0010_kpi
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0011_over_limit"
down_revision = "0010_kpi"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    if table not in set(inspector.get_table_names()):
        return True  # jadval yo'q — qo'shishga urinmaymiz
    return column in {c["name"] for c in inspector.get_columns(table)}


def upgrade() -> None:
    if not _has_column("orders", "over_limit_reason"):
        op.add_column("orders", sa.Column("over_limit_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    if _has_column("orders", "over_limit_reason"):
        op.drop_column("orders", "over_limit_reason")
