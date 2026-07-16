"""reconcile the stamped legacy database with the analysis engine contract

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-16

The shared database was stamped at 0001 after its schema had been created by
the prototype. In that database, ``features.external_id`` was added manually.
Every additive DDL statement is idempotent so fresh and stamped databases
converge on the same schema.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The stamped prototype database uses ``analysisstatus`` while fresh 0001
    # databases use ``analysis_status``. Resolve the physical type from the
    # column so both histories converge without renaming a live shared type.
    enum_reconciliation = """
    DO $migration$
    DECLARE status_type text;
    BEGIN
        SELECT udt_name INTO status_type
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'analysis_runs'
          AND column_name = 'status';
        EXECUTE format(
            'ALTER TYPE %I ADD VALUE IF NOT EXISTS ''pending'' BEFORE ''running''',
            status_type
        );
        EXECUTE format(
            'ALTER TYPE %I ADD VALUE IF NOT EXISTS ''failed'' AFTER ''completed''',
            status_type
        );
    END
    $migration$;
    """
    # PostgreSQL requires added enum values to be committed before they are used.
    with op.get_context().autocommit_block():
        op.execute(enum_reconciliation)

    op.execute("ALTER TABLE features ADD COLUMN IF NOT EXISTS external_id VARCHAR")
    op.execute("ALTER TABLE analysis_runs ADD COLUMN IF NOT EXISTS started_at TIMESTAMPTZ")
    op.execute("ALTER TABLE analysis_runs ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ")
    op.execute("ALTER TABLE analysis_runs ADD COLUMN IF NOT EXISTS duration_ms INTEGER")
    op.execute("ALTER TABLE analysis_runs ADD COLUMN IF NOT EXISTS error JSONB")

    op.execute("UPDATE analysis_runs SET status = 'failed' WHERE status = 'error'")
    op.execute("ALTER TABLE analysis_runs ALTER COLUMN status SET DEFAULT 'pending'")

    op.execute(
        "ALTER TABLE indicator_results ADD COLUMN IF NOT EXISTS "
        "formula_version VARCHAR DEFAULT 'legacy'"
    )
    op.execute(
        "UPDATE indicator_results SET formula_version = 'legacy' WHERE formula_version IS NULL"
    )
    op.alter_column(
        "indicator_results",
        "formula_version",
        existing_type=sa.String(),
        nullable=False,
        server_default=None,
    )
    op.execute("ALTER TABLE indicator_results ADD COLUMN IF NOT EXISTS metric_crs VARCHAR")
    op.execute(
        "ALTER TABLE indicator_results ADD COLUMN IF NOT EXISTS "
        "parameters JSONB NOT NULL DEFAULT '{}'::jsonb"
    )
    op.execute(
        "ALTER TABLE indicator_results ADD COLUMN IF NOT EXISTS "
        "source_layers JSONB NOT NULL DEFAULT '[]'::jsonb"
    )
    op.execute(
        "ALTER TABLE indicator_results ADD COLUMN IF NOT EXISTS "
        "warnings JSONB NOT NULL DEFAULT '[]'::jsonb"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE analysis_runs ALTER COLUMN status SET DEFAULT 'running'")
    op.execute("UPDATE analysis_runs SET status = 'error' WHERE status = 'failed'")

    for column_name in (
        "warnings",
        "source_layers",
        "parameters",
        "metric_crs",
        "formula_version",
    ):
        op.execute(f"ALTER TABLE indicator_results DROP COLUMN IF EXISTS {column_name}")
    for column_name in ("error", "duration_ms", "completed_at", "started_at"):
        op.execute(f"ALTER TABLE analysis_runs DROP COLUMN IF EXISTS {column_name}")

    # external_id belongs to the 0001 target schema and is intentionally kept.
    # Enum values are retained because removing them requires a destructive type
    # rebuild; old application versions can safely ignore the extra values.
