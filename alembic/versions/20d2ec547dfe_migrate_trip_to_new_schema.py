"""migrate trip to new schema

Revision ID: 20d2ec547dfe
Revises: cc214b25b404
Create Date: 2025-01-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "20d2ec547dfe"
down_revision: Union[str, Sequence[str], None] = "cc214b25b404"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # Create trip_via_airports table first (before removing old fields)
    result = conn.execute(sa.text("""
        SELECT COUNT(*) as cnt FROM information_schema.tables 
        WHERE table_schema = DATABASE() 
        AND table_name = 'trip_via_airports'
    """))
    if result.fetchone()[0] == 0:
        op.create_table(
            "trip_via_airports",
            sa.Column("via_id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column(
                "trip_id",
                sa.BigInteger(),
                sa.ForeignKey("trips.trip_id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("airport_code", sa.String(length=3), nullable=False),
            sa.Column("via_order", sa.SmallInteger(), nullable=False),
            sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index(
            "ix_trip_via_airports_trip_order",
            "trip_via_airports",
            ["trip_id", "via_order"],
        )

    # Add new columns to trips table (check if they exist first)
    def column_exists(table_name: str, column_name: str) -> bool:
        result = conn.execute(sa.text("""
            SELECT COUNT(*) as cnt FROM information_schema.columns 
            WHERE table_schema = DATABASE() 
            AND table_name = :table_name 
            AND column_name = :column_name
        """), {"table_name": table_name, "column_name": column_name})
        return result.fetchone()[0] > 0

    if not column_exists("trips", "title"):
        op.add_column("trips", sa.Column("title", sa.String(length=200), nullable=True))
    if not column_exists("trips", "note"):
        op.add_column("trips", sa.Column("note", sa.Text(), nullable=True))
    if not column_exists("trips", "from_airport"):
        op.add_column("trips", sa.Column("from_airport", sa.String(length=3), nullable=True))
    if not column_exists("trips", "to_airport"):
        op.add_column("trips", sa.Column("to_airport", sa.String(length=3), nullable=True))
    if not column_exists("trips", "country_from"):
        op.add_column("trips", sa.Column("country_from", sa.String(length=2), nullable=True))
    if not column_exists("trips", "country_to"):
        op.add_column("trips", sa.Column("country_to", sa.String(length=2), nullable=True))
    if not column_exists("trips", "route_type"):
        op.add_column(
            "trips",
            sa.Column(
                "route_type",
                sa.Enum("domestic", "international", name="trip_route_type"),
                nullable=True,
            ),
        )
    if not column_exists("trips", "active"):
        op.add_column(
            "trips",
            sa.Column("active", sa.Boolean(), nullable=True, server_default=sa.false()),
        )
    if not column_exists("trips", "tags_json"):
        op.add_column("trips", sa.Column("tags_json", mysql.JSON(), nullable=True))
    if not column_exists("trips", "archived_at"):
        op.add_column("trips", sa.Column("archived_at", sa.TIMESTAMP(), nullable=True))

    # Create new indexes (check if they exist first)
    def index_exists(table_name: str, index_name: str) -> bool:
        result = conn.execute(sa.text("""
            SELECT COUNT(*) as cnt FROM information_schema.statistics 
            WHERE table_schema = DATABASE() 
            AND table_name = :table_name 
            AND index_name = :index_name
        """), {"table_name": table_name, "index_name": index_name})
        return result.fetchone()[0] > 0

    if not index_exists("trips", "ix_trips_active"):
        op.create_index("ix_trips_active", "trips", ["user_id", "active"])
    if not index_exists("trips", "ix_trips_archived_at"):
        op.create_index("ix_trips_archived_at", "trips", ["user_id", "archived_at"])

    # Drop old indexes
    result = conn.execute(sa.text("""
        SELECT COUNT(*) as cnt FROM information_schema.statistics 
        WHERE table_schema = DATABASE() 
        AND table_name = 'trips' 
        AND index_name = 'ix_trips_country_airline'
    """))
    if result.fetchone()[0] > 0:
        op.drop_index("ix_trips_country_airline", table_name="trips")

    # Drop old columns from trips table (check if they exist first)
    if column_exists("trips", "city"):
        op.drop_column("trips", "city")
    if column_exists("trips", "country_code2"):
        op.drop_column("trips", "country_code2")
    if column_exists("trips", "airline_code"):
        op.drop_column("trips", "airline_code")
    if column_exists("trips", "has_rescreening"):
        op.drop_column("trips", "has_rescreening")


def downgrade() -> None:
    conn = op.get_bind()

    # Restore old columns
    op.add_column("trips", sa.Column("city", sa.String(length=80), nullable=True))
    op.add_column("trips", sa.Column("country_code2", sa.String(length=2), nullable=False))
    op.add_column("trips", sa.Column("airline_code", sa.String(length=8), nullable=True))
    op.add_column(
        "trips",
        sa.Column("has_rescreening", sa.Boolean(), nullable=True, server_default=sa.false()),
    )

    # Restore old index
    op.create_index("ix_trips_country_airline", "trips", ["country_code2", "airline_code"])

    # Drop new indexes
    result = conn.execute(sa.text("""
        SELECT COUNT(*) as cnt FROM information_schema.statistics 
        WHERE table_schema = DATABASE() 
        AND table_name = 'trips' 
        AND index_name = 'ix_trips_active'
    """))
    if result.fetchone()[0] > 0:
        op.drop_index("ix_trips_active", table_name="trips")

    result = conn.execute(sa.text("""
        SELECT COUNT(*) as cnt FROM information_schema.statistics 
        WHERE table_schema = DATABASE() 
        AND table_name = 'trips' 
        AND index_name = 'ix_trips_archived_at'
    """))
    if result.fetchone()[0] > 0:
        op.drop_index("ix_trips_archived_at", table_name="trips")

    # Drop new columns
    op.drop_column("trips", "archived_at")
    op.drop_column("trips", "tags_json")
    op.drop_column("trips", "active")
    op.drop_column("trips", "route_type")
    op.drop_column("trips", "country_to")
    op.drop_column("trips", "country_from")
    op.drop_column("trips", "to_airport")
    op.drop_column("trips", "from_airport")
    op.drop_column("trips", "note")
    op.drop_column("trips", "title")

    # Drop trip_via_airports table
    result = conn.execute(sa.text("""
        SELECT COUNT(*) as cnt FROM information_schema.tables 
        WHERE table_schema = DATABASE() 
        AND table_name = 'trip_via_airports'
    """))
    if result.fetchone()[0] > 0:
        op.drop_index("ix_trip_via_airports_trip_order", table_name="trip_via_airports")
        op.drop_table("trip_via_airports")

