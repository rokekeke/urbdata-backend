"""add maximum floor-area ratio to lot features

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-17

``ca_max`` is the minimum canonical input for the first density/buildability
increment. It is nullable for legacy data and additive on fresh and stamped
databases.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE features ADD COLUMN IF NOT EXISTS ca_max NUMERIC")


def downgrade() -> None:
    op.execute("ALTER TABLE features DROP COLUMN IF EXISTS ca_max")
