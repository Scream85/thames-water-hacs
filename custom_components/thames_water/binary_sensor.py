"""Binary sensor: daily usage above the spike threshold."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_SPIKE_THRESHOLD, DEFAULT_SPIKE_THRESHOLD
from .coordinator import ThamesWaterConfigEntry
from .entity import ThamesWaterEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ThamesWaterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([ThamesWaterSpikeSensor(entry.runtime_data, entry)])


class ThamesWaterSpikeSensor(ThamesWaterEntity, BinarySensorEntity):
    _attr_translation_key = "usage_spike"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator, entry: ThamesWaterConfigEntry) -> None:
        super().__init__(coordinator, "usage_spike")
        self._threshold = entry.options.get(CONF_SPIKE_THRESHOLD, DEFAULT_SPIKE_THRESHOLD)

    @property
    def is_on(self) -> bool | None:
        usage = self.coordinator.data.daily.latest_usage
        return None if usage is None else usage > self._threshold

    @property
    def extra_state_attributes(self) -> dict:
        d = self.coordinator.data.daily
        return {"threshold_litres": self._threshold, "date": d.latest_date, "usage": d.latest_usage}
