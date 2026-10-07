"""Thames Water Smart Meter integration."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .coordinator import ThamesWaterConfigEntry, ThamesWaterCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ThamesWaterConfigEntry) -> bool:
    """Set up from a config entry."""
    coordinator = ThamesWaterCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    if coordinator.data is None:
        # The first refresh can return without data (e.g. the entry was reloaded
        # while a login was in flight). Never set up entities without data.
        raise ConfigEntryNotReady("Thames Water returned no data yet")
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ThamesWaterConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
