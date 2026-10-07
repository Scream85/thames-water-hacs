"""Tests for setup, entities and statistics, with the Thames Water client mocked."""

from __future__ import annotations

import datetime as dt
import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import requests
from homeassistant.components.recorder.models import StatisticMeanType
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry
from thameswaterapi import AuthenticationError, Tariff

from custom_components.thames_water_meter.const import CONF_SPIKE_THRESHOLD, DOMAIN
from custom_components.thames_water_meter.coordinator import ThamesWaterCoordinator
from custom_components.thames_water_meter.diagnostics import async_get_config_entry_diagnostics

ACCOUNT = 12345678
METER = "M1"
FETCH = ThamesWaterCoordinator, "_fetch"
STATS = "custom_components.thames_water_meter.coordinator.async_add_external_statistics"

UTC = dt.UTC


def _charging_year_start(today: dt.date) -> dt.date:
    return dt.date(today.year if today.month >= 4 else today.year - 1, 4, 1)


# Unit rate (1.5 + 2.5) / 1000 = 0.004 GBP/L and standing charge (100 + 82.5) / 365 = 0.5 GBP/day,
# taking effect on the first day of the current charging year so it is always in force.
TARIFF = Tariff(
    clean_water_rate_per_m3=1.5,
    wastewater_rate_per_m3=2.5,
    water_fixed_per_year=100.0,
    wastewater_fixed_per_year=82.5,
    effective_date=_charging_year_start(dt_util.now().date()),
)


def _raw(daily_days=range(1, 5), tariff=True) -> dict:
    """What `_fetch` returns: four October days and three hours, end-of-hour reads."""
    return {
        "account": ACCOUNT,
        "meter": METER,
        "daily": [SimpleNamespace(start=dt.date(2026, 10, d), usage=100 + d) for d in daily_days],
        "hourly": [
            SimpleNamespace(hour_start=dt.datetime(2026, 10, 4, h, tzinfo=UTC), usage=u, total=t)
            for h, u, t in ((0, 10, 1010), (1, 0, 1010), (2, 5, 1015))
        ],
        "tariff": TARIFF if tariff else None,
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
    entity_id = registry.async_get_entity_id(platform, DOMAIN, f"{ACCOUNT}_{METER}_{key}")
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
    assert float(_state(hass, "sensor", "month_to_date_cost").state) == pytest.approx(3.64)


def _full_day_hourly() -> list[SimpleNamespace]:
    """Two complete days; the quietest hour is 03:00 on the second day."""
    rows, total = [], 1000
    for day in (3, 4):
        for hour in range(24):
            usage = 3 if (day, hour) == (4, 3) else 20
            total += usage
            rows.append(
                SimpleNamespace(
                    hour_start=dt.datetime(2026, 10, day, hour, tzinfo=UTC),
                    usage=usage,
                    total=total,
                )
            )
    return rows


async def test_tariff_rate_sensors_show_the_rates_per_cubic_metre(hass: HomeAssistant) -> None:
    await _setup(hass, _entry(), _raw())

    clean = _state(hass, "sensor", "clean_water_rate")
    assert float(clean.state) == pytest.approx(1.5)
    assert clean.attributes["unit_of_measurement"] == "GBP/m³"
    assert clean.attributes["effective_date"] == TARIFF.effective_date.isoformat()
    assert float(_state(hass, "sensor", "wastewater_rate").state) == pytest.approx(2.5)
    # The combined rate is the sum, the same figure the cost sensors price a litre with.
    assert float(_state(hass, "sensor", "combined_water_rate").state) == pytest.approx(4.0)


async def test_tariff_rate_sensors_have_no_value_without_a_tariff(hass: HomeAssistant) -> None:
    await _setup(hass, _entry(), _raw(tariff=False))

    for key in ("clean_water_rate", "wastewater_rate", "combined_water_rate"):
        assert _state(hass, "sensor", key).state == "unknown"


async def test_the_device_is_not_attributed_to_thames_water(hass: HomeAssistant) -> None:
    """The device page reads "<model> by <manufacturer>", which would say the company made
    this integration, and the account data does not say who made the meter."""
    await _setup(hass, _entry(), _raw())

    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, f"{ACCOUNT}_{METER}")})
    assert device is not None
    assert device.manufacturer is None
    assert device.model == "Thames Water smart meter"


async def test_an_existing_device_loses_the_old_manufacturer(hass: HomeAssistant) -> None:
    """Leaving the manufacturer out of the device info means "keep what is stored", so a
    device created by an earlier version would still read "by Thames Water"."""
    entry = _entry()
    entry.add_to_hass(hass)
    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, f"{ACCOUNT}_{METER}")},
        manufacturer="Thames Water",
        model="Smart water meter",
    )

    with patch.object(*FETCH, return_value=_raw()), patch(STATS):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, f"{ACCOUNT}_{METER}")})
    assert device is not None
    assert device.manufacturer is None
    assert device.model == "Thames Water smart meter"


async def test_minimum_hourly_usage_and_last_data_sensors(hass: HomeAssistant) -> None:
    raw = _raw()
    raw["hourly"] = _full_day_hourly()
    await _setup(hass, _entry(), raw)

    quietest = _state(hass, "sensor", "min_hourly_usage")
    assert float(quietest.state) == 3
    assert quietest.attributes["hour"] == 3
    assert quietest.attributes["date"] == dt.date(2026, 10, 4)

    last = _state(hass, "sensor", "last_data")
    assert dt_util.parse_datetime(last.state) == dt.datetime(2026, 10, 4, 23, tzinfo=UTC)


async def test_minimum_hourly_usage_has_no_value_without_a_complete_day(
    hass: HomeAssistant,
) -> None:
    """The default fixture has three hours, which would read as a quiet day."""
    await _setup(hass, _entry(), _raw())

    assert _state(hass, "sensor", "min_hourly_usage").state == "unknown"


@pytest.mark.parametrize(
    "key",
    ["latest_day_usage", "average_7d", "month_to_date", "meter_reading", "min_hourly_usage"],
)
async def test_litre_sensors_show_whole_litres(hass: HomeAssistant, key: str) -> None:
    """Thames Water reports whole litres, so "345.0 L" is noise."""
    raw = _raw()
    raw["hourly"] = _full_day_hourly()
    await _setup(hass, _entry(), raw)

    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id("sensor", DOMAIN, f"{ACCOUNT}_{METER}_{key}")
    entry = registry.async_get(entity_id)
    assert entry.options["sensor"]["suggested_display_precision"] == 0
    assert entry.unit_of_measurement == "L"


@pytest.mark.parametrize(
    "key",
    ["latest_day_usage", "average_7d", "month_to_date", "meter_reading", "min_hourly_usage"],
)
async def test_each_volume_sensor_has_a_cubic_metre_twin(hass: HomeAssistant, key: str) -> None:
    """The m3 twins line Thames Water up with meters that report m3."""
    raw = _raw()
    raw["hourly"] = _full_day_hourly()
    await _setup(hass, _entry(), raw)

    litres = _state(hass, "sensor", key)
    cubic = _state(hass, "sensor", f"{key}_m3")
    assert cubic.attributes["unit_of_measurement"] == "m³"
    assert litres.attributes["unit_of_measurement"] == "L"
    assert float(cubic.state) == pytest.approx(float(litres.state) / 1000)

    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id("sensor", DOMAIN, f"{ACCOUNT}_{METER}_{key}_m3")
    assert registry.async_get(entity_id).options["sensor"]["suggested_display_precision"] == 3


async def test_cubic_metre_twins_have_no_value_when_the_litre_sensor_has_none(
    hass: HomeAssistant,
) -> None:
    """The default fixture has no complete day, so minimum hourly usage is unknown."""
    await _setup(hass, _entry(), _raw())

    assert _state(hass, "sensor", "min_hourly_usage").state == "unknown"
    assert _state(hass, "sensor", "min_hourly_usage_m3").state == "unknown"


async def test_meter_reading_names_its_statistic(hass: HomeAssistant) -> None:
    await _setup(hass, _entry(), _raw())

    attrs = _state(hass, "sensor", "meter_reading").attributes
    assert attrs["statistic_id"] == "thames_water_meter:m1_water_consumption"
    assert attrs["read_taken_at"] == "end of hour"


async def test_month_to_date_follows_the_latest_data_across_a_month_boundary(
    hass: HomeAssistant,
) -> None:
    """Data lags ~3 days, so early in a month the latest rows are last month's."""
    raw = _raw()
    raw["daily"] = [SimpleNamespace(start=dt.date(2026, 9, d), usage=100) for d in (28, 29, 30)]
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


def _tariff_key(entry: MockConfigEntry) -> str:
    return f"{DOMAIN}.tariff.{entry.entry_id}"


def _saved_tariff(effective_date: dt.date) -> dict:
    """What the integration stores, wrapped the way a Store file is."""
    return {
        "clean_water_rate_per_m3": 1.5,
        "wastewater_rate_per_m3": 2.5,
        "water_fixed_per_year": 100.0,
        "wastewater_fixed_per_year": 82.5,
        "effective_date": effective_date.isoformat(),
    }


def _preload(hass_storage: dict, entry: MockConfigEntry, data: dict) -> None:
    key = _tariff_key(entry)
    hass_storage[key] = {"version": 1, "minor_version": 1, "key": key, "data": data}


async def test_a_fetched_tariff_is_saved_for_the_next_start(
    hass: HomeAssistant, hass_storage: dict
) -> None:
    entry = _entry()
    await _setup(hass, entry, _raw())

    assert hass_storage[_tariff_key(entry)]["data"] == _saved_tariff(TARIFF.effective_date)


async def test_the_saved_tariff_is_used_when_the_tariff_page_cannot_be_read(
    hass: HomeAssistant, hass_storage: dict
) -> None:
    """After a restart nothing is in memory, so cost sensors would be unknown until the
    next successful tariff fetch without this."""
    entry = _entry()
    _preload(hass_storage, entry, _saved_tariff(TARIFF.effective_date))
    await _setup(hass, entry, _raw(tariff=False))

    assert float(_state(hass, "sensor", "latest_day_cost").state) == pytest.approx(0.92)
    assert float(_state(hass, "sensor", "month_to_date_cost").state) == pytest.approx(3.64)


@pytest.mark.parametrize(
    "saved",
    [
        _saved_tariff(dt.date(2020, 4, 1)),  # its charging year ended long ago
        {"clean_water_rate_per_m3": "not a number"},  # unreadable
        {**_saved_tariff(TARIFF.effective_date), "effective_date": "April"},  # bad date
    ],
    ids=["lapsed", "unreadable", "bad-date"],
)
async def test_a_lapsed_or_unreadable_saved_tariff_is_ignored(
    hass: HomeAssistant, hass_storage: dict, saved: dict
) -> None:
    entry = _entry()
    _preload(hass_storage, entry, saved)
    await _setup(hass, entry, _raw(tariff=False))

    assert entry.state is ConfigEntryState.LOADED
    assert _state(hass, "sensor", "latest_day_cost").state == "unknown"


async def test_an_unchanged_tariff_is_not_written_again_on_every_refresh(
    hass: HomeAssistant, hass_storage: dict
) -> None:
    entry = _entry()
    await _setup(hass, entry, _raw())

    with (
        patch.object(*FETCH, return_value=_raw()),
        patch(STATS),
        patch("homeassistant.helpers.storage.Store.async_save") as save,
    ):
        await entry.runtime_data.async_refresh()
        await entry.runtime_data.async_refresh()

    save.assert_not_called()


async def test_removing_the_entry_deletes_the_saved_tariff(
    hass: HomeAssistant, hass_storage: dict
) -> None:
    entry = _entry()
    await _setup(hass, entry, _raw())
    assert _tariff_key(entry) in hass_storage

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    assert _tariff_key(entry) not in hass_storage


async def test_hourly_statistics_are_imported_at_their_real_times(
    hass: HomeAssistant,
) -> None:
    entry = _entry()
    entry.add_to_hass(hass)
    with patch.object(*FETCH, return_value=_raw()), patch(STATS) as add_stats:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    metadata, stats = _imported(add_stats, "thames_water_meter:m1_water_consumption")
    assert metadata["statistic_id"] == "thames_water_meter:m1_water_consumption"
    assert metadata["has_sum"] is True
    assert metadata["mean_type"] is StatisticMeanType.NONE
    assert metadata["unit_of_measurement"] == "L"
    assert [s["start"].hour for s in stats] == [0, 1, 2]
    assert [s["sum"] for s in stats] == [1010, 1010, 1015]


async def test_placeholder_hours_without_a_meter_read_are_not_imported(
    hass: HomeAssistant,
) -> None:
    raw = _raw()
    raw["hourly"].append(
        SimpleNamespace(hour_start=dt.datetime(2026, 10, 4, 3, tzinfo=UTC), usage=0, total=0)
    )
    entry = _entry()
    entry.add_to_hass(hass)
    with patch.object(*FETCH, return_value=raw), patch(STATS) as add_stats:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    _metadata, stats = _imported(add_stats, "thames_water_meter:m1_water_consumption")
    assert [s["sum"] for s in stats] == [1010, 1010, 1015]


def _imported(add_stats, statistic_id: str):
    """The (metadata, stats) of the one import made for a statistic id."""
    calls = [c for c in add_stats.call_args_list if c.args[1]["statistic_id"] == statistic_id]
    assert len(calls) == 1, [c.args[1]["statistic_id"] for c in add_stats.call_args_list]
    return calls[0].args[1], calls[0].args[2]


COST_ID = "thames_water_meter:m1_water_cost"
# The default fixture: hours of 10, 0 and 5 litres, 4.0 GBP/m3 (0.004 per litre), and a standing
# charge of 0.5 a day, so each hour carries 0.5 / 24 of it.
HOUR_COSTS = [10 * 0.004 + 0.5 / 24, 0 * 0.004 + 0.5 / 24, 5 * 0.004 + 0.5 / 24]


async def test_each_hour_is_costed_into_a_second_statistic(
    hass: HomeAssistant, stored_statistics
) -> None:
    """The Energy dashboard cannot price an imported consumption, so the cost is imported too."""
    entry = _entry()
    entry.add_to_hass(hass)
    with patch.object(*FETCH, return_value=_raw()), patch(STATS) as add_stats:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    metadata, stats = _imported(add_stats, COST_ID)
    assert metadata["name"] == "Thames Water M1 cost"
    assert metadata["unit_of_measurement"] == "GBP"
    assert metadata["has_sum"] is True
    assert metadata["has_mean"] is False
    assert metadata["mean_type"] is StatisticMeanType.NONE
    assert metadata["unit_class"] is None
    assert [s["start"].hour for s in stats] == [0, 1, 2]
    expected, total = [], 0.0
    for cost in HOUR_COSTS:
        total += cost
        expected.append(total)
    assert [s["sum"] for s in stats] == pytest.approx(expected, abs=1e-5)
    # The three hours add up to the volume charge plus 3/24 of the daily standing charge.
    assert stats[-1]["sum"] == pytest.approx(15 * 0.004 + 3 * 0.5 / 24, abs=1e-5)


async def test_the_cost_total_continues_from_what_is_already_stored(
    hass: HomeAssistant, stored_statistics
) -> None:
    """Importing a window again must not restart the total from zero."""
    stored_statistics.rows[COST_ID] = [{"start": 0.0, "sum": 40.0}, {"start": 3600.0, "sum": 50.0}]
    entry = _entry()
    entry.add_to_hass(hass)
    with patch.object(*FETCH, return_value=_raw()), patch(STATS) as add_stats:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    _metadata, stats = _imported(add_stats, COST_ID)
    assert stats[0]["sum"] == pytest.approx(50.0 + HOUR_COSTS[0], abs=1e-5)  # the latest stored
    assert stats[-1]["sum"] == pytest.approx(50.0 + sum(HOUR_COSTS), abs=1e-5)
    # It looked for what precedes the first imported hour, within the week before it.
    start, end, ids = stored_statistics.reads[0]
    assert ids == {COST_ID}
    assert end == dt.datetime(2026, 10, 4, 0, tzinfo=UTC)
    assert end - start == dt.timedelta(days=7)


async def test_no_cost_is_imported_without_a_tariff(hass: HomeAssistant) -> None:
    entry = _entry()
    entry.add_to_hass(hass)
    with patch.object(*FETCH, return_value=_raw(tariff=False)), patch(STATS) as add_stats:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    ids = [c.args[1]["statistic_id"] for c in add_stats.call_args_list]
    assert ids == ["thames_water_meter:m1_water_consumption"]


async def test_hours_before_the_rates_took_effect_are_not_costed(hass: HomeAssistant) -> None:
    """Only the current scheme of charges is known, so earlier hours get no cost."""
    raw = _raw()
    raw["tariff"] = Tariff(
        clean_water_rate_per_m3=1.5,
        wastewater_rate_per_m3=2.5,
        water_fixed_per_year=100.0,
        wastewater_fixed_per_year=82.5,
        effective_date=dt.date(2026, 10, 5),  # the day after the hours in the fixture
    )
    entry = _entry()
    entry.add_to_hass(hass)
    with patch.object(*FETCH, return_value=raw), patch(STATS) as add_stats:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    ids = [c.args[1]["statistic_id"] for c in add_stats.call_args_list]
    assert ids == ["thames_water_meter:m1_water_consumption"]


async def test_the_cost_statistic_id_is_shown_on_the_cost_sensor(hass: HomeAssistant) -> None:
    await _setup(hass, _entry(), _raw())

    assert _state(hass, "sensor", "month_to_date_cost").attributes["statistic_id"] == COST_ID


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


async def test_diagnostics_hold_no_credentials_or_identifiers(hass: HomeAssistant) -> None:
    raw = _raw()
    raw["meter"] = "AB123456"
    entry = _entry(options={CONF_SPIKE_THRESHOLD: 500})
    await _setup(hass, entry, raw)

    result = await async_get_config_entry_diagnostics(hass, entry)

    text = json.dumps(result)  # must be plain JSON, which is what the download needs
    for secret in ("hunter2", "someone@example.com", str(ACCOUNT), "AB123456"):
        assert secret not in text
    assert result["entry"]["data"]["password"] == "**REDACTED**"
    assert result["entry"]["data"]["email"] == "**REDACTED**"
    assert result["entry"]["options"] == {CONF_SPIKE_THRESHOLD: 500}
    assert result["account"] == "******78"
    assert result["meter"] == "******56"
    assert result["coordinator"]["last_update_success"] is True
    assert result["coordinator"]["older_history_imported"] is False  # _fetch is mocked here
    assert result["daily"]["latest_usage"] == 104
    assert result["daily"]["latest_date"] == "2026-10-04"
    assert result["latest_hour"] == "2026-10-04T02:00:00+00:00"
    assert result["tariff"]["clean_water_rate_per_m3"] == 1.5


async def test_diagnostics_work_without_a_tariff(hass: HomeAssistant) -> None:
    entry = _entry()
    await _setup(hass, entry, _raw(tariff=False))

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["tariff"] is None
    json.dumps(result)


async def test_unloading_removes_the_entities(hass: HomeAssistant) -> None:
    entry = _entry()
    await _setup(hass, entry, _raw())

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert _state(hass, "sensor", "latest_day_usage").state == "unavailable"
