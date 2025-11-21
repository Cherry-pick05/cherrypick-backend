"""merge country_airport and trip_segments branches

Revision ID: e25da4bf8e62
Revises: b3c4d5e6f7g8, 7c2bb0e9d2d3
Create Date: 2025-11-21 19:53:05.205198

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e25da4bf8e62'
down_revision: Union[str, Sequence[str], None] = ('b3c4d5e6f7g8', '7c2bb0e9d2d3')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
