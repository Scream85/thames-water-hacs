"""Tests for setup, entities and statistics, with the Thames Water client mocked."""

from __future__ import annotations

import datetime as dt
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import requests
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry
from thameswaterapi import AuthenticationError

from custom_components.thames_water.const import CONF_SPIKE_THRESHOLD, DOMAIN
from custom_components.thames_water.coordinator import ThamesWaterCoordinator

ACCOUNT = 12345678
METER = "M1"
FETCH = ThamesWaterCoordinator, "_fetch"
STATS = "custom_components.thames_water.coordinator.async_add_external_statistics"

UTC = dt.timezone.utc


def _raw(daily_days=range(1, 5), tariff=True) -> dict:
    """What `_fetch` returns: four October days and three hours, end-of-hour reads."""
    return {
        "account": ACCOUNT,
        "meter": METER,
        "daily": [
            SimpleNamespace(start=dt.date(2026, 10, d), usage=100 + d)
            for d in daily_days
        ],
        "hourly": [
            SimpleNamespace(
                hour_start=dt.datetime(2026, 10, 4, h, tzinfo=UTC), usage=u, total=t
            )
            for h, u, t in ((0, 10, 1010), (1, 0, 1010), (2, 5, 1015))
        ],
        "tariff": (
            SimpleNamespace(unit_rate_per_litre=0.004, standing_charge_per_day=0.5)
            if tariff
            else None
        ),
    }


def _entry(**kwargs) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=str(ACCOUNT),
        data={"email": "someone@example.com", "password": "hunter2"},
        **kwargs,
    )


async def _setup(hass: HomeAssistant, entry: MockConfigEntry, raw: dict) -> None:
    entry.add_to_hass(hass)
    with patch.object(*FETCH, return_value=raw), patch(STATS):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()


def _state(hass: HomeAssistant, platform: str, key: str):
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(
        platform, DOMAIN, f"{ACCOUNT}_{METER}_{key}"
    )
    assert entity_id is not None, f"no {platform} entity for {key}"
    return hass.states.get(entity_id)


async def test_entities_report_the_derived_figures(hass: HomeAssistant) -> None:
    entry = _entry()
    await _setup(hass, entry, _raw())

    assert entry.state is ConfigEntryState.LOADED
    assert float(_state(hass, "sensor", "latest_day_usage").state) == 104
    assert float(_state(hass, "sensor", "average_7d").state) == pytest.approx(102.5)
    month = _state(hass, "sensor", "month_to_date")
    assert float(month.state) == 410
    assert month.attributes["month"] == "2026-10"
    assert float(_state(hass, "sensor", "meter_reading").state) == 1015
    assert float(_state(hass, "sensor", "latest_day_cost").state) == pytest.approx(0.92)
    assert float(_state(hass, "sensor", "month_to_date_cost").state) == pytest.approx(
        3.64
    )


async def test_meter_reading_names_its_statistic(hass: HomeAssistant) -> None:
    await _setup(hass, _entry(), _raw())

    attrs = _state(hass, "sensor", "meter_reading").attributes
    assert attrs["statistic_id"] == "thames_water:m1_water_consumption"
    assert attrs["read_taken_at"] == "end of hour"


async def test_month_to_date_follows_the_latest_data_across_a_month_boundary(
    hass: HomeAssistant,
) -> None:
    """Data lags ~3 days, so early in a month the latest rows are last month's."""
    raw = _raw()
    raw["daily"] = [
        SimpleNamespace(start=dt.date(2026, 9, d), usage=100) for d in (28, 29, 30)
    ]
    await _setup(hass, _entry(), raw)

    month = _state(hass, "sensor", "month_to_date")
    assert float(month.state) == 300
    assert month.attributes["month"] == "2026-09"


async def test_cost_sensors_have_no_value_without_a_tariff(
    hass: HomeAssistant,
) -> None:
    await _setup(hass, _entry(), _raw(tariff=False))

    assert _state(hass, "sensor", "latest_day_cost").state == "unknown"
    assert _state(hass, "sensor", "month_to_date_cost").state == "unknown"
    assert float(_state(hass, "sensor", "latest_day_usage").state) == 104


async def test_hourly_statistics_are_imported_at_their_real_times(
    hass: HomeAssistant,
) -> None:
    entry = _entry()
    entry.add_to_hass(hass)
    with patch.object(*FETCH, return_value=_raw()), patch(STATS) as add_stats:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    add_stats.assert_called_once()
    _hass, metadata, stats = add_stats.call_args.args
    assert metadata["statistic_id"] == "thames_water:m1_water_consumption"
    assert metadata["has_sum"] is True
    assert metadata["unit_of_measurement"] == "L"
    assert [s["start"].hour for s in stats] == [0, 1, 2]
    assert [s["sum"] for s in stats] == [1010, 1010, 1015]


async def test_placeholder_hours_without_a_meter_read_are_not_imported(
    hass: HomeAssistant,
) -> None:
    raw = _raw()
    raw["hourly"].append(
        SimpleNamespace(
            hour_start=dt.datetime(2026, 10, 4, 3, tzinfo=UTC), usage=0, total=0
        )
    )
    entry = _entry()
    entry.add_to_hass(hass)
    with patch.object(*FETCH, return_value=raw), patch(STATS) as add_stats:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    stats = add_stats.call_args.args[2]
    assert [s["sum"] for s in stats] == [1010, 1010, 1015]


@pytest.mark.parametrize(
    ("threshold", "expected"), [(None, "off"), (100, "on")], ids=["default", "low"]
)
async def test_spike_sensor_follows_the_threshold(
    hass: HomeAssistant, threshold: int | None, expected: str
) -> None:
    options = {} if threshold is None else {CONF_SPIKE_THRESHOLD: threshold}
    await _setup(hass, _entry(options=options), _raw())

    assert _state(hass, "binary_sensor", "usage_spike").state == expected


async def test_a_rejected_login_starts_reauth(hass: HomeAssistant) -> None:
    entry = _entry()
    entry.add_to_hass(hass)
    with patch.object(*FETCH, side_effect=AuthenticationError("rejected")):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert [f["context"]["source"] for f in flows] == ["reauth"]


async def test_an_unreachable_site_retries_setup(hass: HomeAssistant) -> None:
    entry = _entry()
    entry.add_to_hass(hass)
    with patch.object(*FETCH, side_effect=requests.ConnectionError("down")):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_unloading_removes_the_entities(hass: HomeAssistant) -> None:
    entry = _entry()
    await _setup(hass, entry, _raw())

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert _state(hass, "sensor", "latest_day_usage").state == "unavailable"
