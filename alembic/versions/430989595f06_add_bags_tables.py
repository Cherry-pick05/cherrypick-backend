"""add bags tables

Revision ID: 430989595f06
Revises: e25da4bf8e62
Create Date: 2025-11-22 17:22:55.101247

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "430989595f06"
down_revision: Union[str, Sequence[str], None] = "e25da4bf8e62"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

BAG_TYPE_ENUM = sa.Enum("carry_on", "checked", "custom", name="bag_type")
BAG_ITEM_STATUS = sa.Enum("todo", "packed", name="bag_item_status")


def upgrade() -> None:
    conn = op.get_bind()
    BAG_TYPE_ENUM.create(conn, checkfirst=True)
    BAG_ITEM_STATUS.create(conn, checkfirst=True)

    op.create_table(
        "bags",
        sa.Column("bag_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "trip_id",
            sa.BigInteger(),
            sa.ForeignKey("trips.trip_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("bag_type", BAG_TYPE_ENUM, nullable=False, server_default="custom"),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sort_order", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            server_onupdate=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint("bag_id", "trip_id", name="uq_bags_id_trip"),
    )
    op.create_index("ix_bags_trip_id", "bags", ["trip_id"])
    op.create_index("ix_bags_user_updated_at", "bags", ["user_id", "updated_at"])

    op.create_table(
        "bag_items",
        sa.Column("item_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "trip_id",
            sa.BigInteger(),
            sa.ForeignKey("trips.trip_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "bag_id",
            sa.BigInteger(),
            sa.ForeignKey("bags.bag_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "regulation_match_id",
            sa.BigInteger(),
            sa.ForeignKey("regulation_matches.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("status", BAG_ITEM_STATUS, nullable=False, server_default="todo"),
        sa.Column("quantity", sa.SmallInteger(), nullable=False, server_default="1"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("preview_snapshot", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            server_onupdate=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(
            ["bag_id", "trip_id"],
            ["bags.bag_id", "bags.trip_id"],
            name="fk_bag_items_bag_trip",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_bag_items_bag_status", "bag_items", ["bag_id", "status", "updated_at"])
    op.create_index("ix_bag_items_user_updated", "bag_items", ["user_id", "updated_at"])


def downgrade() -> None:
    conn = op.get_bind()

    op.drop_index("ix_bag_items_user_updated", table_name="bag_items")
    op.drop_index("ix_bag_items_bag_status", table_name="bag_items")
    op.drop_table("bag_items")

    op.drop_index("ix_bags_user_updated_at", table_name="bags")
    op.drop_index("ix_bags_trip_id", table_name="bags")
    op.drop_table("bags")

    BAG_ITEM_STATUS.drop(conn, checkfirst=True)
    BAG_TYPE_ENUM.drop(conn, checkfirst=True)
