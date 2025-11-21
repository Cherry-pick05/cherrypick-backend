"""expand trips with segments

Revision ID: b3c4d5e6f7g8
Revises: a2f0f7c1f6d8
Create Date: 2025-01-20 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b3c4d5e6f7g8"
down_revision: Union[str, Sequence[str], None] = "a2f0f7c1f6d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create trip_segments table
    op.create_table(
        "trip_segments",
        sa.Column("segment_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "trip_id",
            sa.BigInteger(),
            sa.ForeignKey("trips.trip_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("segment_order", sa.SmallInteger(), nullable=False),
        sa.Column("direction", sa.String(length=16), nullable=False),  # 'outbound' or 'return'
        sa.Column("departure_airport", sa.String(length=3), nullable=False),
        sa.Column("arrival_airport", sa.String(length=3), nullable=False),
        sa.Column("departure_country", sa.String(length=2), nullable=False),
        sa.Column("arrival_country", sa.String(length=2), nullable=False),
        sa.Column("operating_airline", sa.String(length=8), nullable=True),
        sa.Column("cabin_class", sa.String(length=32), nullable=True),
        sa.Column("departure_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            server_onupdate=sa.text("CURRENT_TIMESTAMP"),
        ),
    )

    op.create_index(
        "ix_trip_segments_trip_order",
        "trip_segments",
        ["trip_id", "segment_order"],
    )
    op.create_index(
        "ix_trip_segments_direction",
        "trip_segments",
        ["trip_id", "direction"],
    )

    # Add rescreening flag to trips (for security checkpoint rules)
    op.add_column(
        "trips",
        sa.Column("has_rescreening", sa.Boolean(), nullable=True, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_index("ix_trip_segments_direction", table_name="trip_segments")
    op.drop_index("ix_trip_segments_trip_order", table_name="trip_segments")
    op.drop_table("trip_segments")
    op.drop_column("trips", "has_rescreening")

