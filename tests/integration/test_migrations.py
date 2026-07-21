import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

TEST_DATABASE_URL = os.getenv("URBDATA_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="URBDATA_TEST_DATABASE_URL is required for destructive migration tests",
)


def _config() -> Config:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", TEST_DATABASE_URL or "")
    return config


def _database_url() -> str:
    assert TEST_DATABASE_URL is not None
    return TEST_DATABASE_URL


def test_fresh_and_stamped_legacy_database_converge_to_head() -> None:
    config = _config()
    command.upgrade(config, "0001")
    # Mirrors the shared database history: existing schema registered as 0001.
    command.stamp(config, "0001")
    command.upgrade(config, "head")

    engine = create_engine(_database_url())
    with engine.connect() as connection:
        assert (
            connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            == "0010"
        )
    columns = {column["name"] for column in inspect(engine).get_columns("indicator_results")}
    assert {
        "formula_version",
        "metric_crs",
        "parameters",
        "source_layers",
        "warnings",
        "value_json",
    } <= columns
    feature_columns = {column["name"] for column in inspect(engine).get_columns("features")}
    assert "external_id" in feature_columns
    assert {
        "macroarea",
        "parcelavel",
        "reference_area_m2",
        "quadra_id",
        "road_status",
        "ca_max",
    } <= feature_columns
    export_columns = {column["name"] for column in inspect(engine).get_columns("exports")}
    assert {"status", "completed_at", "error"} <= export_columns
    layer_columns = {column["name"] for column in inspect(engine).get_columns("project_layers")}
    assert {
        "import_profile",
        "attributes_filename",
        "attributes_join_key",
        "geometry_join_key",
        "join_summary",
    } <= layer_columns

    command.downgrade(config, "0001")
    command.upgrade(config, "head")
    with engine.connect() as connection:
        assert (
            connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            == "0010"
        )
