"""Shartnoma jadvallarida `created_at` uchun server default'ini tiklash.

0006 da bu ustunlar `server_default`siz yaratilgan edi. Modeldagi
`TimestampMixin` esa qiymatni bazadan kutadi (`server_default=func.now()`),
shuning uchun INSERT paytida NULL tushib, "not-null constraint" xatosi
chiqardi — direktor tarif yaratganda 500 shundan edi.

Toza bazada bu muammo ko'rinmagan: `0001_initial` jadvallarni
`create_all` bilan yaratadi va u default'ni o'zi qo'yadi.

Revision ID: 0007_contract_defaults
Revises: 0006_contracts
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007_contract_defaults"
down_revision = "0006_contracts"
branch_labels = None
depends_on = None

JADVALLAR = ("tariffs", "contracts")
USTUNLAR = ("created_at", "updated_at")


def _mavjud(table: str) -> bool:
    return table in set(sa.inspect(op.get_bind()).get_table_names())


def _sqlite() -> bool:
    """SQLite `ALTER COLUMN`ni qo'llab-quvvatlamaydi.

    U yerda jadvallar `0001_initial` dagi `create_all` bilan yaratiladi va
    default allaqachon joyida — tuzatish kerak emas.
    """
    return op.get_bind().dialect.name == "sqlite"


def upgrade() -> None:
    if _sqlite():
        return
    for table in JADVALLAR:
        if not _mavjud(table):
            continue
        for column in USTUNLAR:
            op.alter_column(
                table,
                column,
                existing_type=sa.DateTime(timezone=True),
                existing_nullable=False,
                server_default=sa.text("now()"),
            )


def downgrade() -> None:
    if _sqlite():
        return
    for table in JADVALLAR:
        if not _mavjud(table):
            continue
        for column in USTUNLAR:
            op.alter_column(
                table,
                column,
                existing_type=sa.DateTime(timezone=True),
                existing_nullable=False,
                server_default=None,
            )
