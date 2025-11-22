"""add needs_duration flag to trips

Revision ID: 1b4a0c1ef8d2
Revises: e25da4bf8e62
Create Date: 2025-11-22 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "1b4a0c1ef8d2"
down_revision: Union[str, Sequence[str], None] = "e25da4bf8e62"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "trips",
        sa.Column(
            "needs_duration",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )
    op.execute(
        sa.text(
            """
            UPDATE trips
            SET needs_duration = FALSE
            WHERE start_date IS NOT NULL AND end_date IS NOT NULL
            """
        )
    )


def downgrade() -> None:
    op.drop_column("trips", "needs_duration")


