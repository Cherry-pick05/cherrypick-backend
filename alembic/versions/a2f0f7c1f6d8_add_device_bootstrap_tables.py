"""add device bootstrap tables

Revision ID: a2f0f7c1f6d8
Revises: 2b4cb2d0f923
Create Date: 2025-11-19 11:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a2f0f7c1f6d8"
down_revision: Union[str, Sequence[str], None] = "2b4cb2d0f923"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "last_seen_at",
            sa.TIMESTAMP(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "flags",
            sa.JSON(),
            nullable=True,
        ),
    )

    op.create_table(
        "user_consents",
        sa.Column("consent_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.user_id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("terms_required", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("privacy_required", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("marketing_opt_in", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("crash_opt_in", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("consent_version", sa.String(length=20), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            server_onupdate=sa.text("CURRENT_TIMESTAMP"),
        ),
    )

    op.create_table(
        "device_recovery_codes",
        sa.Column("code_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code_hash", sa.String(length=128), nullable=False),
        sa.Column("previous_device_uuid", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("expires_at", sa.TIMESTAMP(), nullable=False),
        sa.Column("redeemed_at", sa.TIMESTAMP(), nullable=True),
        sa.Column("revoked_at", sa.TIMESTAMP(), nullable=True),
        sa.UniqueConstraint("code_hash", name="uq_device_recovery_codes_hash"),
    )
    op.create_index(
        "ix_device_recovery_user",
        "device_recovery_codes",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_device_recovery_user", table_name="device_recovery_codes")
    op.drop_table("device_recovery_codes")
    op.drop_table("user_consents")
    op.drop_column("users", "flags")
    op.drop_column("users", "last_seen_at")

