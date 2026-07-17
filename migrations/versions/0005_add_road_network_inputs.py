"""add road-network source classification and space-syntax unlink layer

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-17

The uploaded centerline remains the source of truth. ``road_status`` records
whether each source feature is existing or proposed. A separate point layer
marks planar crossings that must not connect topologically (space-syntax
``unlink`` semantics). Both additions are nullable/additive for the stamped
legacy database.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The stamped prototype can have a physical enum name different from the
    # canonical ``layer_type``. Resolve it from the column, as revision 0002
    # already does for analysis status.
    enum_reconciliation = """
    DO $migration$
    DECLARE layer_type_name text;
    BEGIN
        SELECT udt_name INTO layer_type_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'project_layers'
          AND column_name = 'layer_type';
        EXECUTE format(
            'ALTER TYPE %I ADD VALUE IF NOT EXISTS ''desconexoes_viarias''',
            layer_type_name
        );
    END
    $migration$;
    """
    with op.get_context().autocommit_block():
        op.execute(enum_reconciliation)

    op.execute("ALTER TABLE features ADD COLUMN IF NOT EXISTS road_status VARCHAR")
    op.execute("CREATE INDEX IF NOT EXISTS ix_features_road_status ON features (road_status)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_features_road_status")
    op.execute("ALTER TABLE features DROP COLUMN IF EXISTS road_status")
    # Enum values are intentionally retained: PostgreSQL requires a destructive
    # type rebuild to remove one, and older application versions safely ignore it.
