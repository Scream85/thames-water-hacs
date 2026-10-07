"""Base entity."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ThamesWaterCoordinator


class ThamesWaterEntity(CoordinatorEntity[ThamesWaterCoordinator]):
    """Base class: one device per Thames Water account/meter."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: ThamesWaterCoordinator, key: str) -> None:
        super().__init__(coordinator)
        data = coordinator.data
        self._attr_unique_id = f"{data.account_number}_{data.meter}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{data.account_number}_{data.meter}")},
            name=f"Thames Water meter {data.meter}",
            # No manufacturer: "by Thames Water" would say the company makes this integration,
            # and the meter's real maker is not something the account data tells us. It is set
            # to None on purpose. Leaving it out means "keep what is stored", so a device
            # created by an earlier version would still read "by Thames Water".
            manufacturer=None,
            model="Thames Water smart meter",
        )
