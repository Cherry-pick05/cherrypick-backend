"""rename us rule codes to iso

Revision ID: f2a1d3c4e5b6
Revises: e25da4bf8e62
Create Date: 2025-11-24 05:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f2a1d3c4e5b6"
down_revision: Union[str, Sequence[str], None] = "e25da4bf8e62"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    def fetch_id(code: str) -> int | None:
        result = conn.execute(
            sa.text(
                "SELECT id FROM rule_sets WHERE scope='country' AND code=:code LIMIT 1"
            ),
            {"code": code},
        )
        row = result.fetchone()
        return row[0] if row else None

    target_id = fetch_id("US")
    if not target_id:
        tsa_id = fetch_id("US_TSA")
        if tsa_id:
            conn.execute(
                sa.text("UPDATE rule_sets SET code='US' WHERE id=:id"),
                {"id": tsa_id},
            )
            target_id = tsa_id

    packsafe_ids_result = conn.execute(
        sa.text(
            "SELECT id FROM rule_sets WHERE scope='country' AND code IN ('US_PACKSAFE', 'US_PACKSAFE_MD')"
        )
    )
    packsafe_ids = [row[0] for row in packsafe_ids_result.fetchall()]

    if not target_id and packsafe_ids:
        target_id = packsafe_ids[0]
        conn.execute(
            sa.text("UPDATE rule_sets SET code='US' WHERE id=:id"),
            {"id": target_id},
        )
        packsafe_ids = packsafe_ids[1:]

    if target_id:
        for pack_id in packsafe_ids:
            conn.execute(
                sa.text(
                    "UPDATE item_rules SET rule_set_id=:target WHERE rule_set_id=:source"
                ),
                {"target": target_id, "source": pack_id},
            )
            conn.execute(
                sa.text("DELETE FROM rule_sets WHERE id=:id"), {"id": pack_id}
            )


def downgrade() -> None:
    conn = op.get_bind()
    result = conn.execute(
        sa.text("SELECT id FROM rule_sets WHERE scope='country' AND code='US' LIMIT 1")
    )
    row = result.fetchone()
    if row:
        conn.execute(
            sa.text("UPDATE rule_sets SET code='US_TSA' WHERE id=:id"), {"id": row[0]}
        )

