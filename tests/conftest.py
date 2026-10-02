from __future__ import annotations

import pytest

import src.database.connection as connection
from src.config import get_settings


@pytest.fixture(autouse=True)
async def isolated_database(tmp_path, monkeypatch):
    monkeypatch.setenv("THAMES_WATER_API_KEY", "admin-test-key")
    monkeypatch.setenv("INGEST_API_KEY", "hands-test-key")
    monkeypatch.setenv("DB_PATH", str(tmp_path / "water.db"))
    monkeypatch.setenv("NOTIFICATION_EMAIL", "")
    get_settings.cache_clear()
    connection._db = None
    database = connection.get_database()
    await database.connect()
    try:
        yield database
    finally:
        await database.disconnect()
        connection._db = None
        get_settings.cache_clear()
