"""merge needs_duration and bags branches

Revision ID: 7606c95b1551
Revises: 1b4a0c1ef8d2, 430989595f06
Create Date: 2025-11-23 00:31:30.784748

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7606c95b1551'
down_revision: Union[str, Sequence[str], None] = ('1b4a0c1ef8d2', '430989595f06')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
