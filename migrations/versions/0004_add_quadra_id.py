"""add features.quadra_id (ADR 009)

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-17

Raw grouping key from the source export (e.g. the `QUADRA` field) used to
derive quadra geometries by dissolving the lots that share a value -
distinct from `parent_quadra_feature_id`, which is only set once a quadra
Feature has actually been materialized from this grouping. Additive and
idempotent.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE features ADD COLUMN IF NOT EXISTS quadra_id VARCHAR")
    op.execute("CREATE INDEX IF NOT EXISTS ix_features_quadra_id ON features (quadra_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_features_quadra_id")
    op.execute("ALTER TABLE features DROP COLUMN IF EXISTS quadra_id")
