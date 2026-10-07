"""Sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

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


@dataclass(frozen=True, kw_only=True)
class ThamesWaterSensorDescription(SensorEntityDescription):
    value_fn: Callable[[ThamesWaterData], float | None]
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
        value_fn=lambda d: d.daily.month_to_date,
        attrs_fn=lambda d: {"month": d.daily.month, "days": d.daily.month_days},
    ),
    ThamesWaterSensorDescription(
        key="meter_reading",
        translation_key="meter_reading",
        device_class=SensorDeviceClass.WATER,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        value_fn=lambda d: d.latest_meter_read,
        attrs_fn=lambda d: {
            "as_of": d.latest_hour,
            "statistic_id": d.statistic_id,
            "read_taken_at": "start of hour" if d.read_is_start_of_hour else "end of hour",
        },
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
        attrs_fn=lambda d: {"month": d.daily.month, "days": d.daily.month_days},
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ThamesWaterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(ThamesWaterSensor(coordinator, d) for d in SENSORS)


class ThamesWaterSensor(ThamesWaterEntity, SensorEntity):
    entity_description: ThamesWaterSensorDescription

    def __init__(self, coordinator, description: ThamesWaterSensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float | None:
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.attrs_fn is None:
            return None
        return self.entity_description.attrs_fn(self.coordinator.data)
