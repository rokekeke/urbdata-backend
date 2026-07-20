"""Structural guard against the shared-database leak (Obsidian nota 37).

Root cause: `test_analysis_api.py` only read `URBDATA_TEST_DATABASE_URL`
to decide whether to *skip*; the app's real connection reads
`URBDATA_DATABASE_URL`, which defaults to the shared `urbdata` database.
Every prior integration run silently wrote test data there.

This must run in `pytest_configure`, not a fixture: `app/main.py` executes
`app = create_app()` (calling `get_settings()`, `@lru_cache`d) at IMPORT
time, and pytest imports test modules during collection - before any
fixture, even an autouse session-scoped one, gets a chance to run.
`pytest_configure` is the earliest hook available, always before
collection starts.
"""

import os

import pytest


def pytest_configure(config: pytest.Config) -> None:
    test_url = os.environ.get("URBDATA_TEST_DATABASE_URL")
    if not test_url:
        pytest.exit(
            "URBDATA_TEST_DATABASE_URL nao definida. Testes de integracao "
            "exigem um banco isolado e descartavel explicito - sem essa "
            "variavel, URBDATA_DATABASE_URL cairia no default do Settings "
            "(o banco compartilhado 'urbdata', com dado real) e a "
            "aplicacao escreveria la silenciosamente. Ver nota Obsidian 37.",
            returncode=1,
        )
    # Set BEFORE any test module imports app.main/app.config.settings, so
    # get_settings() never sees the shared-database default.
    os.environ["URBDATA_DATABASE_URL"] = test_url
