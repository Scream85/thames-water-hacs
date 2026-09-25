from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.api.routes import router


def payload(usage_litres: float = 420.0) -> dict:
    return {
        "daily": [
            {
                "date": "2026-09-21",
                "usage_litres": usage_litres,
                "meter_reading": 123456.0,
                "is_estimated": False,
            }
        ],
        "hourly": [
            {
                "date": "2026-09-21",
                "hour": 7,
                "usage_litres": 18.5,
                "meter_reading": 123000.0,
                "is_estimated": False,
            }
        ],
        "source": "hands",
    }


@pytest.fixture
async def client():
    app = FastAPI()
    app.include_router(router)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as value:
        yield value


async def test_ingest_auth_missing_and_wrong_key(client):
    missing = await client.post("/api/ingest", json=payload())
    wrong = await client.post(
        "/api/ingest",
        json=payload(),
        headers={"X-Ingest-Key": "wrong"},
    )

    assert missing.status_code == 401
    assert wrong.status_code == 403


async def test_ingest_fails_closed_when_server_key_is_unset(client, monkeypatch):
    from src.config import get_settings

    monkeypatch.delenv("INGEST_API_KEY")
    get_settings.cache_clear()

    response = await client.post(
        "/api/ingest",
        json=payload(),
        headers={"X-Ingest-Key": "hands-test-key"},
    )

    assert response.status_code == 403


@pytest.mark.parametrize(
    "change",
    [
        {"daily": [{"date": "21-09-2026", "usage_litres": 10}]},
        {"daily": [{"date": "2026-09-21", "usage_litres": -1}]},
        {"hourly": [{"date": "2026-09-21", "hour": 24, "usage_litres": 1}]},
    ],
)
async def test_ingest_rejects_invalid_consumption(client, change):
    body = payload()
    body.update(change)

    response = await client.post(
        "/api/ingest",
        json=body,
        headers={"X-Ingest-Key": "hands-test-key"},
    )

    assert response.status_code == 422


async def test_ingest_is_idempotent_logs_source_and_creates_one_spike_alert(
    client, isolated_database
):
    headers = {"X-Ingest-Key": "hands-test-key"}

    first = await client.post("/api/ingest", json=payload(901), headers=headers)
    second = await client.post("/api/ingest", json=payload(901), headers=headers)

    assert first.status_code == 200
    assert first.json() == {"daily": 1, "hourly": 1}
    assert second.status_code == 200
    assert await isolated_database.fetch_one("SELECT COUNT(*) AS count FROM daily_usage") == {
        "count": 1
    }
    assert await isolated_database.fetch_one("SELECT COUNT(*) AS count FROM hourly_usage") == {
        "count": 1
    }
    assert await isolated_database.fetch_one("SELECT COUNT(*) AS count FROM alerts") == {
        "count": 1
    }
    logs = await isolated_database.fetch_all(
        "SELECT sync_type, source, records_stored FROM sync_log ORDER BY id"
    )
    assert logs == [
        {"sync_type": "ingest", "source": "hands", "records_stored": 2},
        {"sync_type": "ingest", "source": "hands", "records_stored": 2},
    ]
