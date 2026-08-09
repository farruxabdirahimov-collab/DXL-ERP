"""Maqola/video materiallari va rassilkalar.

Revision ID: 0003_content
Revises: 0002_doctor_requests
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0003_content"
down_revision = "0002_doctor_requests"
branch_labels = None
depends_on = None


def _has(table: str) -> bool:
    return table in sa.inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    # Toza bazada `0001_initial` bu jadvallarni modellardan yaratib bo'lgan bo'ladi
    if not _has("posts"):
        op.create_table(
            "posts",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column(
                "kind",
                sa.Enum(
                    "article", "video", "news",
                    name="post_kind_enum", native_enum=False, length=32,
                ),
                nullable=False,
            ),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("summary", sa.String(length=400), nullable=True),
            sa.Column("body", sa.Text(), nullable=True),
            sa.Column("media_url", sa.String(length=500), nullable=True),
            sa.Column("image_url", sa.String(length=500), nullable=True),
            sa.Column("is_published", sa.Boolean(), nullable=False),
            sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("views", sa.Integer(), nullable=False),
            sa.Column("author_id", sa.Integer(), nullable=True),
            sa.Column(
                "created_at", sa.DateTime(timezone=True),
                server_default=sa.text("now()"), nullable=False,
            ),
            sa.Column(
                "updated_at", sa.DateTime(timezone=True),
                server_default=sa.text("now()"), nullable=False,
            ),
            sa.ForeignKeyConstraint(
                ["author_id"], ["users.id"],
                name=op.f("fk_posts_author_id_users"), ondelete="SET NULL",
            ),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_posts")),
        )
        op.create_index(op.f("ix_posts_created_at"), "posts", ["created_at"])
        op.create_index(op.f("ix_posts_is_published"), "posts", ["is_published"])
        op.create_index(op.f("ix_posts_kind"), "posts", ["kind"])
        op.create_index(op.f("ix_posts_published_at"), "posts", ["published_at"])

    if not _has("broadcasts"):
        op.create_table(
            "broadcasts",
            sa.Column("id", sa.BigInteger().with_variant(sa.Integer, "sqlite"), nullable=False),
            sa.Column("text", sa.Text(), nullable=False),
            sa.Column(
                "audience",
                sa.Enum(
                    "all_doctors", "my_doctors", "category_a", "category_b",
                    "category_c", "debtors", "one_doctor", "staff",
                    name="audience_enum", native_enum=False, length=32,
                ),
                nullable=False,
            ),
            sa.Column("doctor_id", sa.Integer(), nullable=True),
            sa.Column("post_id", sa.Integer(), nullable=True),
            sa.Column("sent_count", sa.Integer(), nullable=False),
            sa.Column("failed_count", sa.Integer(), nullable=False),
            sa.Column("created_by_id", sa.Integer(), nullable=True),
            sa.Column(
                "created_at", sa.DateTime(timezone=True),
                server_default=sa.text("now()"), nullable=False,
            ),
            sa.Column(
                "updated_at", sa.DateTime(timezone=True),
                server_default=sa.text("now()"), nullable=False,
            ),
            sa.ForeignKeyConstraint(
                ["created_by_id"], ["users.id"],
                name=op.f("fk_broadcasts_created_by_id_users"), ondelete="SET NULL",
            ),
            sa.ForeignKeyConstraint(
                ["doctor_id"], ["doctors.id"],
                name=op.f("fk_broadcasts_doctor_id_doctors"), ondelete="SET NULL",
            ),
            sa.ForeignKeyConstraint(
                ["post_id"], ["posts.id"],
                name=op.f("fk_broadcasts_post_id_posts"), ondelete="SET NULL",
            ),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_broadcasts")),
        )
        op.create_index(op.f("ix_broadcasts_created_at"), "broadcasts", ["created_at"])


def downgrade() -> None:
    if _has("broadcasts"):
        op.drop_table("broadcasts")
    if _has("posts"):
        op.drop_table("posts")
