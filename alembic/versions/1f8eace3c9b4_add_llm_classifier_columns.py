"""add llm classifier related columns

Revision ID: 1f8eace3c9b4
Revises: cc214b25b404
Create Date: 2025-11-15 06:05:00.000000
"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "1f8eace3c9b4"
down_revision: Union[str, Sequence[str], None] = "cc214b25b404"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(conn, table_name: str, column_name: str) -> bool:
    result = conn.execute(
        sa.text(
            """
            SELECT COUNT(*) as cnt
            FROM information_schema.columns
            WHERE table_schema = DATABASE()
              AND table_name = :table_name
              AND column_name = :column_name
            """
        ),
        {"table_name": table_name, "column_name": column_name},
    )
    return result.fetchone()[0] > 0


def _constraint_exists(conn, table_name: str, constraint_name: str) -> bool:
    result = conn.execute(
        sa.text(
            """
            SELECT COUNT(*) as cnt
            FROM information_schema.table_constraints
            WHERE table_schema = DATABASE()
              AND table_name = :table_name
              AND constraint_name = :constraint_name
            """
        ),
        {"table_name": table_name, "constraint_name": constraint_name},
    )
    return result.fetchone()[0] > 0


def upgrade() -> None:
    conn = op.get_bind()

    # ------------------------------------------------------------------
    # taxonomy
    # ------------------------------------------------------------------
    if not _column_exists(conn, "taxonomy", "display_name"):
        op.add_column("taxonomy", sa.Column("display_name", sa.String(length=64), nullable=True))

    if not _column_exists(conn, "taxonomy", "is_active"):
        op.add_column(
            "taxonomy",
            sa.Column("is_active", sa.SmallInteger(), nullable=False, server_default=sa.text("1")),
        )

    # ------------------------------------------------------------------
    # taxonomy_synonym
    # ------------------------------------------------------------------
    if not _column_exists(conn, "taxonomy_synonym", "priority"):
        op.add_column(
            "taxonomy_synonym",
            sa.Column("priority", sa.SmallInteger(), nullable=False, server_default=sa.text("0")),
        )

    match_type_enum = sa.Enum("exact", "substring", "regex", name="synonym_match_type")
    match_type_enum.create(conn, checkfirst=True)

    if not _column_exists(conn, "taxonomy_synonym", "match_type"):
        op.add_column(
            "taxonomy_synonym",
            sa.Column("match_type", match_type_enum, nullable=False, server_default="substring"),
        )

    if _constraint_exists(conn, "taxonomy_synonym", "uq_synonym"):
        op.drop_constraint("uq_synonym", "taxonomy_synonym", type_="unique")

    op.create_unique_constraint(
        "uq_synonym", "taxonomy_synonym", ["synonym", "match_type"]
    )

    # ------------------------------------------------------------------
    # regulation_matches
    # ------------------------------------------------------------------
    if not _column_exists(conn, "regulation_matches", "req_id"):
        op.add_column("regulation_matches", sa.Column("req_id", sa.String(length=64), nullable=True))

    if not _column_exists(conn, "regulation_matches", "raw_label"):
        op.add_column(
            "regulation_matches",
            sa.Column("raw_label", sa.String(length=256), nullable=True),
        )

    if not _column_exists(conn, "regulation_matches", "norm_label"):
        op.add_column(
            "regulation_matches",
            sa.Column("norm_label", sa.String(length=256), nullable=True),
        )

    if not _column_exists(conn, "regulation_matches", "canonical_key"):
        op.add_column(
            "regulation_matches",
            sa.Column("canonical_key", sa.String(length=64), nullable=True),
        )
        op.create_index(
            "idx_regmatch_canonical",
            "regulation_matches",
            ["canonical_key"],
            unique=False,
        )

    if not _column_exists(conn, "regulation_matches", "candidates_json"):
        op.add_column(
            "regulation_matches",
            sa.Column("candidates_json", sa.JSON(), nullable=True),
        )

    decided_by_enum = sa.Enum(
        "auto",
        "user",
        "llm_classifier",
        "dict_classifier",
        "tiebreak_llm",
        "admin_rule",
        name="match_decider",
    )
    decided_by_enum.create(conn, checkfirst=True)

    if not _column_exists(conn, "regulation_matches", "decided_by"):
        op.add_column(
            "regulation_matches",
            sa.Column(
                "decided_by",
                decided_by_enum,
                nullable=False,
                server_default="auto",
            ),
        )

    if not _column_exists(conn, "regulation_matches", "model_info"):
        op.add_column(
            "regulation_matches",
            sa.Column("model_info", sa.JSON(), nullable=True),
        )


def downgrade() -> None:
    conn = op.get_bind()

    # regulation_matches
    if _column_exists(conn, "regulation_matches", "canonical_key"):
        op.drop_index("idx_regmatch_canonical", table_name="regulation_matches")

    for column in ["model_info", "decided_by", "candidates_json", "canonical_key", "norm_label", "raw_label", "req_id"]:
        if _column_exists(conn, "regulation_matches", column):
            op.drop_column("regulation_matches", column)

    decided_by_enum = sa.Enum(
        "auto",
        "user",
        "llm_classifier",
        "dict_classifier",
        "tiebreak_llm",
        "admin_rule",
        name="match_decider",
    )
    decided_by_enum.drop(conn, checkfirst=True)

    # taxonomy_synonym
    if _constraint_exists(conn, "taxonomy_synonym", "uq_synonym"):
        op.drop_constraint("uq_synonym", "taxonomy_synonym", type_="unique")

    op.create_unique_constraint(
        "uq_synonym", "taxonomy_synonym", ["synonym", "lang"]
    )

    if _column_exists(conn, "taxonomy_synonym", "match_type"):
        op.drop_column("taxonomy_synonym", "match_type")

    match_type_enum = sa.Enum("exact", "substring", "regex", name="synonym_match_type")
    match_type_enum.drop(conn, checkfirst=True)

    if _column_exists(conn, "taxonomy_synonym", "priority"):
        op.drop_column("taxonomy_synonym", "priority")

    # taxonomy
    if _column_exists(conn, "taxonomy", "is_active"):
        op.drop_column("taxonomy", "is_active")

    if _column_exists(conn, "taxonomy", "display_name"):
        op.drop_column("taxonomy", "display_name")

