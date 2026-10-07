"""The cost total continues from what the real recorder holds.

The other tests fake the read, so these run against a real recorder to prove the call and the
shape of what it returns, which is what keeps the running total from restarting at zero.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Generator
from types import SimpleNamespace

import pytest
from homeassistant.components.recorder import Recorder
from homeassistant.components.recorder.models import (
    StatisticData,
    StatisticMeanType,
    StatisticMetaData,
)
from homeassistant.components.recorder.statistics import async_add_external_statistics
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.components.recorder.common import (
    async_wait_recording_done,
)

from custom_components.thames_water_meter.const import DOMAIN
from custom_components.thames_water_meter.coordinator import ThamesWaterCoordinator

STATISTIC_ID = f"{DOMAIN}:m1_water_cost"
UTC = dt.UTC
FIRST_HOUR = dt.datetime(2026, 10, 4, 12, tzinfo=UTC)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations() -> Generator[None]:
    """Do not load the integration: that fixture creates `hass` before the recorder's database
    exists, which a real recorder cannot be set up after. Only one coordinator method is used."""
    yield


@pytest.fixture(autouse=True)
def mock_recorder_before_hass() -> Generator[None]:
    """Use the real recorder here, instead of the stand-in the other tests use."""
    yield


@pytest.fixture(autouse=True)
def stored_statistics() -> Generator[None]:
    """Do not fake the read here: it is the thing under test."""
    yield


def _store(hass: HomeAssistant, hours_before: dict[int, float]) -> None:
    """Write running totals at the given number of hours before FIRST_HOUR."""
    metadata = StatisticMetaData(
        has_mean=False,
        mean_type=StatisticMeanType.NONE,
        has_sum=True,
        name="Thames Water M1 cost",
        source=DOMAIN,
        statistic_id=STATISTIC_ID,
        unit_of_measurement="GBP",
        unit_class=None,
    )
    stats = [
        StatisticData(start=FIRST_HOUR - dt.timedelta(hours=hours), state=total, sum=total)
        for hours, total in hours_before.items()
    ]
    async_add_external_statistics(hass, metadata, sorted(stats, key=lambda s: s["start"]))


async def _sum_before(hass: HomeAssistant) -> float:
    # The method only uses `self.hass`, so a stand-in avoids building a whole coordinator.
    return await ThamesWaterCoordinator._async_sum_before(
        SimpleNamespace(hass=hass), STATISTIC_ID, FIRST_HOUR
    )


async def test_the_total_just_before_the_first_hour_is_read_back(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    _store(hass, {3: 40.0, 2: 45.0, 1: 50.0})
    await async_wait_recording_done(hass)

    assert await _sum_before(hass) == pytest.approx(50.0)


async def test_hours_at_or_after_the_first_hour_are_not_read(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """A stored hour that the window is about to overwrite must not become its base."""
    _store(hass, {1: 50.0, 0: 60.0, -1: 70.0})
    await async_wait_recording_done(hass)

    assert await _sum_before(hass) == pytest.approx(50.0)


async def test_a_gap_in_the_data_still_finds_the_last_total(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    _store(hass, {60: 20.0})  # two and a half days earlier
    await async_wait_recording_done(hass)

    assert await _sum_before(hass) == pytest.approx(20.0)


async def test_nothing_stored_means_the_total_starts_at_zero(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    assert await _sum_before(hass) == 0.0


async def test_a_total_more_than_a_week_earlier_is_not_used(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    _store(hass, {24 * 8: 20.0})
    await async_wait_recording_done(hass)

    assert await _sum_before(hass) == 0.0
