"""initial schema - users va applications jadvallari

Revision ID: 0001_initial
Revises:
Create Date: 2026-07-01

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    application_category = sa.Enum(
        "COMPLAINT",
        "SUGGESTION",
        "REQUEST",
        "QUESTION",
        name="application_category",
    )
    application_status = sa.Enum(
        "NEW",
        "IN_PROGRESS",
        "RESOLVED",
        "REJECTED",
        name="application_status",
    )

    op.create_table(
        "bot_users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("language", sa.String(length=8), nullable=False, server_default="uz"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_bot_users_telegram_id"),
        "bot_users",
        ["telegram_id"],
        unique=True,
    )

    op.create_table(
        "applications",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("category", application_category, nullable=False),
        sa.Column("message_text", sa.Text(), nullable=False),
        sa.Column("attachment_file_id", sa.String(length=255), nullable=True),
        sa.Column("attachment_type", sa.String(length=32), nullable=True),
        sa.Column(
            "status",
            application_status,
            nullable=False,
            server_default="NEW",
        ),
        sa.Column("admin_reply", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["bot_users.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_applications_status"), "applications", ["status"], unique=False
    )
    op.create_index(
        op.f("ix_applications_created_at"),
        "applications",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_applications_created_at"), table_name="applications")
    op.drop_index(op.f("ix_applications_status"), table_name="applications")
    op.drop_table("applications")
    op.drop_index(op.f("ix_bot_users_telegram_id"), table_name="bot_users")
    op.drop_table("bot_users")
    sa.Enum(name="application_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="application_category").drop(op.get_bind(), checkfirst=True)
