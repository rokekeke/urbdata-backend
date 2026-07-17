"""preserve structured indicator result values

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-17

The legacy numeric column remains populated for numeric consumers. JSONB is
the canonical representation because indicator values may also be strings or
structured dictionaries.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE indicator_results ADD COLUMN IF NOT EXISTS value_json JSONB")
    op.execute(
        "UPDATE indicator_results "
        "SET value_json = to_jsonb(value) "
        "WHERE value_json IS NULL AND value IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE indicator_results DROP COLUMN IF EXISTS value_json")
