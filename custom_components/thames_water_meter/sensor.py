"""Sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import EntityCategory, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .analysis import cost
from .coordinator import ThamesWaterConfigEntry, ThamesWaterData
from .entity import ThamesWaterEntity


def _cost_of(data: ThamesWaterData, litres: float | None) -> float | None:
    if data.tariff is None:
        return None
    return cost(litres, data.tariff.unit_rate_per_litre, data.tariff.standing_charge_per_day)


def _month_cost(data: ThamesWaterData) -> float | None:
    if data.tariff is None or data.daily.month_to_date is None:
        return None
    t = data.tariff
    return round(
        data.daily.month_to_date * t.unit_rate_per_litre
        + t.standing_charge_per_day * data.daily.month_days,
        2,
    )


def _tariff_attributes(data: ThamesWaterData) -> dict[str, Any]:
    """When the rates took effect, so a stale figure can be told from a current one."""
    if data.tariff is None:
        return {}
    return {"effective_date": data.tariff.effective_date.isoformat()}


@dataclass(frozen=True, kw_only=True)
class ThamesWaterSensorDescription(SensorEntityDescription):
    value_fn: Callable[[ThamesWaterData], Any]
    attrs_fn: Callable[[ThamesWaterData], dict[str, Any]] | None = None


# NOTE: state_class is deliberately unset. The data is ~3 days old, so letting the
# recorder compile statistics from these states would stamp them at the wrong time.
# Hourly long-term statistics are imported separately at the correct timestamps.
SENSORS: tuple[ThamesWaterSensorDescription, ...] = (
    ThamesWaterSensorDescription(
        key="latest_day_usage",
        translation_key="latest_day_usage",
        device_class=SensorDeviceClass.WATER,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=0,
        value_fn=lambda d: d.daily.latest_usage,
        attrs_fn=lambda d: {"date": d.daily.latest_date},
    ),
    ThamesWaterSensorDescription(
        key="average_7d",
        translation_key="average_7d",
        device_class=SensorDeviceClass.WATER,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=0,
        value_fn=lambda d: d.daily.avg_7d,
    ),
    ThamesWaterSensorDescription(
        key="month_to_date",
        translation_key="month_to_date",
        device_class=SensorDeviceClass.WATER,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=0,
        value_fn=lambda d: d.daily.month_to_date,
        attrs_fn=lambda d: {"month": d.daily.month, "days": d.daily.month_days},
    ),
    ThamesWaterSensorDescription(
        key="meter_reading",
        translation_key="meter_reading",
        device_class=SensorDeviceClass.WATER,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=0,
        value_fn=lambda d: d.latest_meter_read,
        attrs_fn=lambda d: {
            "as_of": d.latest_hour,
            "statistic_id": d.statistic_id,
            "read_taken_at": "start of hour" if d.read_is_start_of_hour else "end of hour",
        },
    ),
    # Water used in the quietest hour of the latest complete day. A figure that
    # stays well above zero overnight points to a leak.
    ThamesWaterSensorDescription(
        key="min_hourly_usage",
        translation_key="min_hourly_usage",
        device_class=SensorDeviceClass.WATER,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=0,
        value_fn=lambda d: d.hourly_minimum.usage if d.hourly_minimum else None,
        attrs_fn=lambda d: (
            {"date": d.hourly_minimum.date, "hour": d.hourly_minimum.hour}
            if d.hourly_minimum
            else {}
        ),
    ),
    ThamesWaterSensorDescription(
        key="last_data",
        translation_key="last_data",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: dt_util.as_utc(d.latest_hour) if d.latest_hour else None,
    ),
    ThamesWaterSensorDescription(
        key="latest_day_cost",
        translation_key="latest_day_cost",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="GBP",
        suggested_display_precision=2,
        value_fn=lambda d: _cost_of(d, d.daily.latest_usage),
    ),
    ThamesWaterSensorDescription(
        key="month_to_date_cost",
        translation_key="month_to_date_cost",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="GBP",
        suggested_display_precision=2,
        value_fn=_month_cost,
        attrs_fn=lambda d: {
            "month": d.daily.month,
            "days": d.daily.month_days,
            "statistic_id": d.cost_statistic_id,
        },
    ),
    # The published metered rates, in GBP per cubic metre as a bill states them. The combined
    # rate is what a litre costs, and can be used as the price in the Energy dashboard.
    # They have no device class, because MONETARY allows only a plain currency as its unit.
    ThamesWaterSensorDescription(
        key="clean_water_rate",
        translation_key="clean_water_rate",
        native_unit_of_measurement="GBP/m³",
        suggested_display_precision=4,
        value_fn=lambda d: d.tariff.clean_water_rate_per_m3 if d.tariff else None,
        attrs_fn=lambda d: _tariff_attributes(d),
    ),
    ThamesWaterSensorDescription(
        key="wastewater_rate",
        translation_key="wastewater_rate",
        native_unit_of_measurement="GBP/m³",
        suggested_display_precision=4,
        value_fn=lambda d: d.tariff.wastewater_rate_per_m3 if d.tariff else None,
        attrs_fn=lambda d: _tariff_attributes(d),
    ),
    ThamesWaterSensorDescription(
        key="combined_water_rate",
        translation_key="combined_water_rate",
        native_unit_of_measurement="GBP/m³",
        suggested_display_precision=4,
        value_fn=lambda d: d.tariff.volumetric_rate_per_m3 if d.tariff else None,
        attrs_fn=lambda d: _tariff_attributes(d),
    ),
)

# The same volume figures in cubic metres, for lining Thames Water up with meters that
# report m3. They are extra entities rather than a choice of unit, so both are always
# there. Thames Water reports whole litres, so three decimals in m3 loses nothing.
CUBIC_METRE_KEYS = (
    "latest_day_usage",
    "average_7d",
    "month_to_date",
    "meter_reading",
    "min_hourly_usage",
)


def _in_cubic_metres(description: ThamesWaterSensorDescription) -> ThamesWaterSensorDescription:
    litres = description.value_fn

    def cubic_metres(data: ThamesWaterData) -> float | None:
        value = litres(data)
        return None if value is None else value / 1000

    return replace(
        description,
        key=f"{description.key}_m3",
        translation_key=f"{description.key}_m3",
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        suggested_display_precision=3,
        value_fn=cubic_metres,
    )


CUBIC_METRE_SENSORS = tuple(_in_cubic_metres(d) for d in SENSORS if d.key in CUBIC_METRE_KEYS)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ThamesWaterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(ThamesWaterSensor(coordinator, d) for d in (*SENSORS, *CUBIC_METRE_SENSORS))


class ThamesWaterSensor(ThamesWaterEntity, SensorEntity):
    entity_description: ThamesWaterSensorDescription

    def __init__(self, coordinator, description: ThamesWaterSensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.attrs_fn is None:
            return None
        return self.entity_description.attrs_fn(self.coordinator.data)
