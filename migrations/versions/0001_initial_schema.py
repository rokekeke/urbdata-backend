"""initial schema

Migrated from the URBDATA prototype backend (projects -> versions -> layers ->
features, validation, analysis, style presets, exports). Ported here once the
relational model was confirmed against real, already-tested data.

Revision ID: 0001
Revises:
Create Date: 2026-07-16

"""

import geoalchemy2
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("municipality", sa.String()),
        sa.Column("state", sa.String()),
        sa.Column("typology", sa.String()),
        sa.Column("approx_area_m2", sa.Numeric()),
        sa.Column("description", sa.Text()),
        sa.Column("team", sa.String()),
        sa.Column("crs_hint", sa.String()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "project_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id"),
            nullable=False,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("description", sa.Text()),
        sa.Column(
            "parent_version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("project_versions.id")
        ),
        sa.Column(
            "status",
            postgresql.ENUM("active", "concluded", "archived", name="project_version_status"),
            server_default="active",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "project_layers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("project_versions.id"),
            nullable=False,
        ),
        sa.Column(
            "layer_type",
            postgresql.ENUM(
                "perimetro",
                "quadras",
                "lotes",
                "sistema_viario",
                "uso_solo",
                "areas_verdes",
                "equipamentos",
                "edificacoes",
                name="layer_type",
            ),
            nullable=False,
        ),
        sa.Column("source_filename", sa.String()),
        sa.Column("geometry_type", sa.String()),
        sa.Column("feature_count", sa.Integer(), server_default="0"),
        sa.Column(
            "status",
            postgresql.ENUM("uploaded", "mapped", "validated", "error", name="layer_status"),
            server_default="uploaded",
        ),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "layer_attribute_mappings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "layer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("project_layers.id"),
            nullable=False,
        ),
        sa.Column("internal_field", sa.String(), nullable=False),
        sa.Column("source_field", sa.String(), nullable=False),
    )

    op.create_table(
        "features",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "layer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("project_layers.id"),
            nullable=False,
        ),
        sa.Column(
            "project_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("project_versions.id"),
            nullable=False,
        ),
        sa.Column("external_id", sa.String(), nullable=True),
        sa.Column(
            "geom", geoalchemy2.Geometry(geometry_type="GEOMETRY", srid=4326), nullable=False
        ),
        sa.Column("source_properties", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("mapped_properties", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("land_use", sa.String(), nullable=True),
        sa.Column(
            "parent_quadra_feature_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("features.id")
        ),
        sa.Column(
            "parent_lote_feature_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("features.id")
        ),
        sa.Column(
            "relation_method",
            postgresql.ENUM(
                "attribute", "spatial", "unresolved", "not_applicable", name="relation_method"
            ),
            server_default="not_applicable",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_features_land_use", "features", ["land_use"])

    op.create_table(
        "validation_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("project_versions.id"),
            nullable=False,
        ),
        sa.Column("run_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "status",
            postgresql.ENUM("running", "completed", "error", name="validation_status"),
            server_default="running",
        ),
    )

    op.create_table(
        "validation_issues",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "validation_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("validation_runs.id"),
            nullable=False,
        ),
        sa.Column(
            "severity",
            postgresql.ENUM("erro", "alerta", "info", name="validation_severity"),
            nullable=False,
        ),
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("layer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("project_layers.id")),
        sa.Column("feature_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("features.id")),
    )

    op.create_table(
        "analysis_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("project_versions.id"),
            nullable=False,
        ),
        sa.Column("run_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "status",
            postgresql.ENUM("running", "completed", "error", name="analysis_status"),
            server_default="running",
        ),
        sa.Column("config", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
    )

    op.create_table(
        "indicator_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "analysis_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("analysis_runs.id"),
            nullable=False,
        ),
        sa.Column("theme", sa.String(), nullable=False),
        sa.Column("indicator_code", sa.String(), nullable=False),
        sa.Column("value", sa.Numeric()),
        sa.Column("unit", sa.String()),
        sa.Column("reference_min", sa.Numeric()),
        sa.Column("reference_max", sa.Numeric()),
        sa.Column(
            "classification",
            postgresql.ENUM("abaixo", "dentro", "acima", name="indicator_classification"),
            nullable=True,
        ),
        sa.Column(
            "contributing_feature_ids", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb")
        ),
    )

    op.create_table(
        "reference_parameters",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("indicator_code", sa.String(), nullable=False),
        sa.Column("theme", sa.String(), nullable=False),
        sa.Column("value_min", sa.Numeric()),
        sa.Column("value_max", sa.Numeric()),
        sa.Column("unit", sa.String()),
        sa.Column("source", sa.String()),
        sa.Column("typology_scope", sa.String()),
        sa.Column("is_default", sa.Boolean(), server_default=sa.true()),
    )

    op.create_table(
        "style_presets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("target", sa.String(), nullable=False),
        sa.Column("definition", postgresql.JSONB(), nullable=False),
        sa.Column("is_default", sa.Boolean(), server_default=sa.false()),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id")),
    )

    op.create_table(
        "exports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("project_versions.id"),
            nullable=False,
        ),
        sa.Column(
            "analysis_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("analysis_runs.id")
        ),
        sa.Column("format", sa.String(), nullable=False),
        sa.Column("config", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("file_path", sa.String()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("exports")
    op.drop_table("style_presets")
    op.drop_table("reference_parameters")
    op.drop_table("indicator_results")
    op.drop_table("analysis_runs")
    op.drop_table("validation_issues")
    op.drop_table("validation_runs")
    op.drop_index("ix_features_land_use", table_name="features")
    op.drop_table("features")
    op.drop_table("layer_attribute_mappings")
    op.drop_table("project_layers")
    op.drop_table("project_versions")
    op.drop_table("projects")

    for enum_name in (
        "indicator_classification",
        "analysis_status",
        "validation_severity",
        "validation_status",
        "relation_method",
        "layer_status",
        "layer_type",
        "project_version_status",
    ):
        postgresql.ENUM(name=enum_name).drop(op.get_bind(), checkfirst=True)
