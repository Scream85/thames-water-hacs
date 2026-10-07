"""Data coordinator: logs in, fetches usage, imports hourly long-term statistics."""

from __future__ import annotations

import datetime as dt
import logging
import re
from dataclasses import dataclass, field
from typing import Any

import requests
from homeassistant.components.recorder.models import (
    StatisticData,
    StatisticMeanType,
    StatisticMetaData,
)
from homeassistant.components.recorder.statistics import async_add_external_statistics
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util
from thameswaterapi import (
    LONDON,
    AuthenticationError,
    HourlyMeasurement,
    MalformedResponse,
    Measurement,
    RateLimitError,
    Tariff,
    TariffError,
    ThamesWater,
    lines_to_timeseries,
    meter_usage_lines_to_timeseries,
)

from .analysis import (
    DailyMetrics,
    HourlyMinimum,
    cumulative_sum,
    daily_metrics,
    minimum_hourly_usage,
    reads_are_start_of_hour,
)
from .const import DOMAIN, HOURLY_LOOKBACK_DAYS, UPDATE_INTERVAL
from .diagnostics import describe_response

_LOGGER = logging.getLogger(__name__)


class _DiagClient(ThamesWater):
    """ThamesWater client that remembers the last HTTP response for diagnostics."""

    last_response = None

    def _request(self, method, url, **kwargs):
        resp = super()._request(method, url, **kwargs)
        self.last_response = resp
        return resp


@dataclass
class ThamesWaterData:
    """Everything the entities need."""

    account_number: int
    meter: str
    daily: DailyMetrics
    latest_meter_read: float | None
    latest_hour: dt.datetime | None
    tariff: Tariff | None
    statistic_id: str
    read_is_start_of_hour: bool = False
    hourly_minimum: HourlyMinimum | None = None
    extra: dict[str, Any] = field(default_factory=dict)


type ThamesWaterConfigEntry = ConfigEntry[ThamesWaterCoordinator]


class ThamesWaterCoordinator(DataUpdateCoordinator[ThamesWaterData]):
    """Fetch Thames Water data."""

    config_entry: ThamesWaterConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ThamesWaterConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=UPDATE_INTERVAL,
        )
        self._tariff: Tariff | None = None

    # ---- blocking part, runs in the executor -------------------------------
    def _fetch(self) -> dict[str, Any]:
        # Fresh client + full password login every cycle. Do NOT reuse a stored
        # refresh token: that path yields an id_token without the B2C session
        # cookies, and establishing the myaccount session then fails with
        # "no id_token in the login page body".
        client = _DiagClient(
            email=self.config_entry.data[CONF_EMAIL],
            password=self.config_entry.data[CONF_PASSWORD],
        )
        try:
            client.authenticate()
            meters = client.get_meters()
        except MalformedResponse:
            _LOGGER.warning(
                "Thames Water returned an unexpected page. Last response: %s",
                describe_response(client.last_response),
            )
            raise
        if not meters.Meters:
            raise UpdateFailed("No meters found on this Thames Water account")
        meter = meters.Meters[0]

        daily: list[Measurement] = lines_to_timeseries(meters.Lines)

        end = dt.datetime.now(LONDON).date()
        start = end - dt.timedelta(days=HOURLY_LOOKBACK_DAYS)
        usage = client.get_meter_usage(meter, start, end, "H")
        hourly: list[HourlyMeasurement] = meter_usage_lines_to_timeseries(start, usage.Lines)

        try:
            tariff = client.get_tariff()
        except (TariffError, requests.RequestException) as err:
            _LOGGER.debug("Tariff lookup failed, keeping previous: %s", err)
            tariff = None

        return {
            "account": client.account_number,
            "meter": meter,
            "daily": daily,
            "hourly": hourly,
            "tariff": tariff,
        }

    # ---- coordinator -------------------------------------------------------
    async def _async_update_data(self) -> ThamesWaterData:
        try:
            raw = await self.hass.async_add_executor_job(self._fetch)
        except AuthenticationError as err:
            raise ConfigEntryAuthFailed("Thames Water login failed") from err
        except RateLimitError as err:
            raise UpdateFailed(
                f"Rate limited by Thames Water (retry after {err.retry_after}s)"
            ) from err
        except (requests.RequestException, MalformedResponse) as err:
            raise UpdateFailed(f"Error talking to Thames Water: {err}") from err

        if raw["tariff"] is not None:
            self._tariff = raw["tariff"]

        # Drop placeholder rows (no meter read yet) so sums never fall back to 0.
        hourly: list[HourlyMeasurement] = sorted(
            (h for h in raw["hourly"] if h.total > 0), key=lambda h: h.hour_start
        )
        start_of_hour = reads_are_start_of_hour(hourly)
        statistic_id = f"{DOMAIN}:{_slug(raw['meter'])}_water_consumption"

        self._import_statistics(raw["meter"], statistic_id, hourly, start_of_hour)

        latest = hourly[-1] if hourly else None
        return ThamesWaterData(
            account_number=raw["account"],
            meter=raw["meter"],
            daily=daily_metrics(raw["daily"]),
            latest_meter_read=cumulative_sum(latest, start_of_hour) if latest else None,
            latest_hour=latest.hour_start if latest else None,
            tariff=self._tariff,
            statistic_id=statistic_id,
            read_is_start_of_hour=start_of_hour,
            hourly_minimum=minimum_hourly_usage(hourly),
        )

    def _import_statistics(
        self,
        meter: str,
        statistic_id: str,
        hourly: list[HourlyMeasurement],
        start_of_hour: bool,
    ) -> None:
        """Write hourly rows at their real timestamps (data is ~3 days old).

        'sum' is the cumulative meter read in litres, so re-importing the same
        hours is idempotent and the series is anchored to the physical meter.
        """
        if not hourly:
            return
        stats: list[StatisticData] = []
        for h in hourly:
            total = cumulative_sum(h, start_of_hour)
            stats.append(
                StatisticData(
                    start=dt_util.as_utc(h.hour_start),
                    state=total,
                    sum=total,
                )
            )
        metadata = StatisticMetaData(
            has_mean=False,
            mean_type=StatisticMeanType.NONE,
            has_sum=True,
            name=f"Thames Water {meter} consumption",
            source=DOMAIN,
            statistic_id=statistic_id,
            unit_of_measurement=UnitOfVolume.LITERS,
            unit_class="volume",
        )
        async_add_external_statistics(self.hass, metadata, stats)


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9_]", "_", value.lower())
