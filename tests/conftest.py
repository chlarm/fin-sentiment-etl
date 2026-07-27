"""
Shared fixtures. The `engine` fixture connects to the real local Postgres
(same one docker-compose brings up) — these are integration tests for the DQ
checks, which are SQL-heavy enough that mocking them would just be
re-describing the SQL in Python. Skips the whole session cleanly if the local
DB isn't up rather than failing every test with a connection error.
"""
from __future__ import annotations
import pytest
from sqlalchemy.exc import OperationalError

from src.config import Settings
from src.common.db import get_engine


@pytest.fixture(scope="session")
def engine():
    settings = Settings()
    eng = get_engine(settings)
    try:
        with eng.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
    except OperationalError:
        pytest.skip("local Postgres is not reachable (docker compose up -d postgres)")
    return eng
