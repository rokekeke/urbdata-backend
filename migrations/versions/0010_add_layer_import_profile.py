"""add layer import_profile and join traceability columns (nota 53/54 checkpoint)

Revision ID: 0010
Revises: 0009
Create Date: 2026-07-21

Adds support for the combined/split import path: a GeoJSON geometry file
can now be paired with a separate CSV attributes file, joined by an
explicit key instead of arriving pre-merged. ``import_profile`` defaults
to ``combined`` so every existing layer keeps its current (GeoJSON-only)
behaviour unchanged. The four nullable columns only get populated when
``import_profile='split'``; ``geometry_join_key`` staying NULL means
``feature.id`` was used as the join key (the default), not that the key
is unknown.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    import_profile = postgresql.ENUM("combined", "split", name="import_profile")
    import_profile.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "project_layers",
        sa.Column(
            "import_profile", import_profile, nullable=False, server_default="combined"
        ),
    )
    op.add_column("project_layers", sa.Column("attributes_filename", sa.String()))
    op.add_column("project_layers", sa.Column("attributes_join_key", sa.String()))
    op.add_column("project_layers", sa.Column("geometry_join_key", sa.String()))
    op.add_column("project_layers", sa.Column("join_summary", postgresql.JSONB()))


def downgrade() -> None:
    op.drop_column("project_layers", "join_summary")
    op.drop_column("project_layers", "geometry_join_key")
    op.drop_column("project_layers", "attributes_join_key")
    op.drop_column("project_layers", "attributes_filename")
    op.drop_column("project_layers", "import_profile")
    postgresql.ENUM(name="import_profile").drop(op.get_bind(), checkfirst=True)
