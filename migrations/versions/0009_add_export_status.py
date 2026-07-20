"""add export lifecycle status (Fase 5, ADR 014 Decisao 6 checkpoint 5.1)

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-20

The ``exports`` table was ported from the prototype (migration 0001)
without a status column, even though ADR 014 Decisao 6 already describes
a job-shaped contract (POST creates with status, GET polls). Adds
``status`` (enum mirroring ``AnalysisStatus`` - pending/running/completed/
failed; ``running`` deliberately reserved/unused until a real render
queue exists, per the 5.1 checkpoint), ``completed_at`` and ``error``
(mirrors analysis_runs' failure-reporting shape). Does NOT add
``started_at``/``duration_ms`` - analysis_runs has them, but no export
code path sets them yet (server never times a client-side render); add
when a real use appears.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    export_status = postgresql.ENUM(
        "pending", "running", "completed", "failed", name="export_status"
    )
    export_status.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "exports",
        sa.Column("status", export_status, nullable=False, server_default="pending"),
    )
    op.add_column("exports", sa.Column("completed_at", sa.DateTime(timezone=True)))
    op.add_column("exports", sa.Column("error", postgresql.JSONB()))


def downgrade() -> None:
    op.drop_column("exports", "error")
    op.drop_column("exports", "completed_at")
    op.drop_column("exports", "status")
    postgresql.ENUM(name="export_status").drop(op.get_bind(), checkfirst=True)
