"""add country and airport tables

Revision ID: 7c2bb0e9d2d3
Revises: 20d2ec547dfe
Create Date: 2025-11-21 15:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7c2bb0e9d2d3"
down_revision: Union[str, Sequence[str], None] = "20d2ec547dfe"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "countries",
        sa.Column("code", sa.String(length=2), primary_key=True),
        sa.Column("iso3_code", sa.String(length=3), nullable=True),
        sa.Column("name_en", sa.String(length=120), nullable=False),
        sa.Column("name_ko", sa.String(length=120), nullable=False),
        sa.Column("region_group", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
            server_onupdate=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index("ix_countries_name_en", "countries", ["name_en"])
    op.create_index("ix_countries_name_ko", "countries", ["name_ko"])

    op.create_table(
        "airports",
        sa.Column("airport_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("iata_code", sa.String(length=3), nullable=False),
        sa.Column("icao_code", sa.String(length=4), nullable=True),
        sa.Column("name_en", sa.String(length=150), nullable=False),
        sa.Column("name_ko", sa.String(length=150), nullable=True),
        sa.Column("city_en", sa.String(length=120), nullable=True),
        sa.Column("city_ko", sa.String(length=120), nullable=True),
        sa.Column("region_group", sa.String(length=64), nullable=True),
        sa.Column(
            "country_code",
            sa.String(length=2),
            sa.ForeignKey("countries.code", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
            server_onupdate=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint("iata_code", name="uq_airports_iata_code"),
    )
    op.create_index("ix_airports_country_code", "airports", ["country_code"])
    op.create_index("ix_airports_name_en", "airports", ["name_en"])
    op.create_index("ix_airports_name_ko", "airports", ["name_ko"])


def downgrade() -> None:
    op.drop_index("ix_airports_name_ko", table_name="airports")
    op.drop_index("ix_airports_name_en", table_name="airports")
    op.drop_index("ix_airports_country_code", table_name="airports")
    op.drop_table("airports")

    op.drop_index("ix_countries_name_ko", table_name="countries")
    op.drop_index("ix_countries_name_en", table_name="countries")
    op.drop_table("countries")


