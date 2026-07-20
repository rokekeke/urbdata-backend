"""add map_documents table

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-19

Editable cartographic composition (ADR 014). New table, not an ALTER on an
existing one - `config` holds the JSONB payload validated by
`app.domain.cartography.document.MapDocumentConfig` at the application
layer; this migration only creates the storage shape.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "map_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("project_versions.id"),
            nullable=False,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("config", postgresql.JSONB(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("schema_version", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_map_documents_project_version_id", "map_documents", ["project_version_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_map_documents_project_version_id", table_name="map_documents")
    op.drop_table("map_documents")
