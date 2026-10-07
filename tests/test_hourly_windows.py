"""Tests for how many days of hourly data are requested, with a fake Thames Water client."""

from __future__ import annotations

import datetime as dt
from types import SimpleNamespace
from unittest.mock import patch

import requests
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from thameswaterapi import LONDON

from custom_components.thames_water_meter.const import (
    DOMAIN,
    HOURLY_BACKFILL_DAYS,
    HOURLY_RECENT_DAYS,
)

ACCOUNT = 12345678
COORDINATOR = "custom_components.thames_water_meter.coordinator"
STATS = f"{COORDINATOR}.async_add_external_statistics"


def _hour(day: int, hour: int, usage: int, total: int) -> SimpleNamespace:
    return SimpleNamespace(
        hour_start=dt.datetime(2026, 9, day, hour, tzinfo=LONDON), usage=usage, total=total
    )


# The older window ends where the recent one starts, and Thames Water repeats the
# boundary hour in both. The recent window's figure for it must win.
OLDER = [_hour(1, 0, 5, 1005), _hour(1, 1, 99, 1104)]
RECENT = [_hour(1, 1, 7, 1012), _hour(1, 2, 3, 1015)]


class FakeClient:
    """Stands in for ThamesWater: records hourly requests and answers by window."""

    requests: list[tuple[dt.date, dt.date]] = []
    older_error: Exception | None = None

    def __init__(self, email: str, password: str) -> None:
        self.account_number = ACCOUNT
        self.last_response = None

    def authenticate(self) -> None:
        return None

    def get_meters(self) -> SimpleNamespace:
        return SimpleNamespace(Meters=["M1"], Lines=[])

    def get_meter_usage(self, meter, start, end, granularity) -> SimpleNamespace:
        assert granularity == "H"
        FakeClient.requests.append((start, end))
        recent_start = dt.datetime.now(LONDON).date() - dt.timedelta(days=HOURLY_RECENT_DAYS)
        if start < recent_start:
            if FakeClient.older_error:
                raise FakeClient.older_error
            return SimpleNamespace(Lines=OLDER)
        return SimpleNamespace(Lines=RECENT)

    def get_tariff(self):
        return None


def _entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=str(ACCOUNT),
        data={"email": "someone@example.com", "password": "hunter2"},
    )


async def _set_up(hass: HomeAssistant, entry: MockConfigEntry):
    FakeClient.requests = []
    FakeClient.older_error = None
    entry.add_to_hass(hass)
    with (
        patch(f"{COORDINATOR}._DiagClient", FakeClient),
        patch(f"{COORDINATOR}.lines_to_timeseries", lambda lines: []),
        patch(f"{COORDINATOR}.meter_usage_lines_to_timeseries", lambda start, lines: lines),
        patch(STATS) as add_stats,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return add_stats


async def test_first_refresh_fetches_the_recent_window_then_the_older_history(
    hass: HomeAssistant,
) -> None:
    today = dt.datetime.now(LONDON).date()
    recent_start = today - dt.timedelta(days=HOURLY_RECENT_DAYS)
    older_start = today - dt.timedelta(days=HOURLY_BACKFILL_DAYS)

    add_stats = await _set_up(hass, _entry())

    assert FakeClient.requests == [(recent_start, today), (older_start, recent_start)]
    stats = add_stats.call_args.args[2]
    assert [s["sum"] for s in stats] == [1005, 1012, 1015]  # one row per hour, recent wins


async def test_later_refreshes_fetch_only_the_recent_window(hass: HomeAssistant) -> None:
    entry = _entry()
    await _set_up(hass, entry)
    FakeClient.requests = []

    with (
        patch(f"{COORDINATOR}._DiagClient", FakeClient),
        patch(f"{COORDINATOR}.lines_to_timeseries", lambda lines: []),
        patch(f"{COORDINATOR}.meter_usage_lines_to_timeseries", lambda start, lines: lines),
        patch(STATS),
    ):
        await entry.runtime_data.async_refresh()

    today = dt.datetime.now(LONDON).date()
    assert FakeClient.requests == [(today - dt.timedelta(days=HOURLY_RECENT_DAYS), today)]


async def test_a_failed_history_fetch_does_not_fail_setup_and_is_retried(
    hass: HomeAssistant,
) -> None:
    entry = _entry()
    FakeClient.older_error = None
    entry.add_to_hass(hass)
    patches = (
        patch(f"{COORDINATOR}._DiagClient", FakeClient),
        patch(f"{COORDINATOR}.lines_to_timeseries", lambda lines: []),
        patch(f"{COORDINATOR}.meter_usage_lines_to_timeseries", lambda start, lines: lines),
        patch(STATS),
    )
    FakeClient.requests = []
    with patches[0], patches[1], patches[2], patches[3] as add_stats:
        FakeClient.older_error = requests.ConnectionError("history unavailable")
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.LOADED
        assert [s["sum"] for s in add_stats.call_args.args[2]] == [1012, 1015]  # recent only

        # The history is wanted again on the next refresh, and now it arrives.
        FakeClient.older_error = None
        await entry.runtime_data.async_refresh()
        assert [s["sum"] for s in add_stats.call_args.args[2]] == [1005, 1012, 1015]
