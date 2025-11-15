"""make regulation_match.image_id nullable

Revision ID: 2b4cb2d0f923
Revises: 1f8eace3c9b4
Create Date: 2025-11-15 06:45:00.000000
"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "2b4cb2d0f923"
down_revision: Union[str, Sequence[str], None] = "1f8eace3c9b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "regulation_matches",
        "image_id",
        existing_type=sa.BigInteger(),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "regulation_matches",
        "image_id",
        existing_type=sa.BigInteger(),
        nullable=False,
    )

