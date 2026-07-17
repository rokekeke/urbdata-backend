"""add territorial macroarea layer type and feature columns (ADR 008)

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-17

Adds the ``territorio`` value to the ``layer_type`` enum (a single upload
containing every territorial subdivision, tagged per-feature via
``macroarea``) and three new, optional ``features`` columns: ``macroarea``,
``parcelavel``, ``reference_area_m2``. All additive and idempotent, safe on
both a fresh database and the shared dev database.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # PostgreSQL requires added enum values to be committed before they are
    # used (same pattern as revision 0002's analysis_status reconciliation).
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE layer_type ADD VALUE IF NOT EXISTS 'territorio'")

    op.execute("ALTER TABLE features ADD COLUMN IF NOT EXISTS macroarea VARCHAR")
    op.execute("ALTER TABLE features ADD COLUMN IF NOT EXISTS parcelavel BOOLEAN")
    op.execute("ALTER TABLE features ADD COLUMN IF NOT EXISTS reference_area_m2 NUMERIC")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_features_macroarea ON features (macroarea)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_features_macroarea")
    for column_name in ("reference_area_m2", "parcelavel", "macroarea"):
        op.execute(f"ALTER TABLE features DROP COLUMN IF EXISTS {column_name}")

    # The 'territorio' enum value is retained: removing it requires a
    # destructive type rebuild, and old application versions can safely
    # ignore the extra value (same rationale as revision 0002).
