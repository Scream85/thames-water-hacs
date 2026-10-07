"""Fixtures for the Thames Water integration tests.

The two autouse fixtures follow the pattern in jelmer/homeassistant-thameswater
(Apache-2.0), tests/conftest.py: enable custom integrations, and stand in for the
recorder the manifest depends on.
"""

from __future__ import annotations

from collections.abc import Generator
from typing import Any
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(
    enable_custom_integrations: None,
) -> Generator[None]:
    """Let Home Assistant load `custom_components` during a test."""
    yield


@pytest.fixture(autouse=True)
def mock_recorder_before_hass() -> Generator[None]:
    """Stand in for the recorder the manifest depends on.

    Setting a real one up needs a database prepared before `hass` exists.
    Statistics writes are asserted on `async_add_external_statistics` instead.
    """
    with patch("homeassistant.components.recorder.async_setup", return_value=True):
        yield


class StoredStatistics:
    """What the fake recorder holds: rows per statistic id, and the reads made of it."""

    def __init__(self) -> None:
        self.rows: dict[str, list[dict[str, Any]]] = {}
        self.reads: list[tuple[Any, Any, set[str]]] = []


@pytest.fixture(autouse=True)
def stored_statistics() -> Generator[StoredStatistics]:
    """Stand in for reading back statistics already stored in the recorder.

    The cost statistic continues its running total from the last stored value, which is read
    from the recorder. The recorder is not set up in these tests, so only that read is faked.
    A test fills `rows` to give the running total something to continue from.
    """
    stored = StoredStatistics()

    def during_period(hass, start, end, statistic_ids, period, units, types):
        stored.reads.append((start, end, set(statistic_ids)))
        found = {}
        for sid in statistic_ids:
            # Like the recorder: rows whose hour starts in [start, end), oldest first.
            rows = [
                row
                for row in stored.rows.get(sid, [])
                if start.timestamp() <= row["start"] < end.timestamp()
            ]
            if rows:
                found[sid] = sorted(rows, key=lambda row: row["start"])
        return found

    class Instance:
        async def async_add_executor_job(self, function, *args):
            return function(*args)

    with (
        patch(
            "custom_components.thames_water_meter.coordinator.get_instance", lambda hass: Instance()
        ),
        patch(
            "custom_components.thames_water_meter.coordinator.statistics_during_period",
            during_period,
        ),
    ):
        yield stored
