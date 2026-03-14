"""Switch platform for One2Track — setting toggles."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CMD_STEP_COUNTER, DOMAIN
from .coordinator import One2TrackCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up One2Track setting switches."""
    coordinator: One2TrackCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    async_add_entities(
        [One2TrackStepCounterSwitch(coordinator, device["uuid"]) for device in coordinator.device_list]
    )


class One2TrackStepCounterSwitch(CoordinatorEntity[One2TrackCoordinator], SwitchEntity):
    """Switch to enable/disable the step counter on the watch."""

    _attr_has_entity_name = True
    _attr_translation_key = "step_counter"
    _attr_icon = "mdi:shoe-print"

    def __init__(self, coordinator: One2TrackCoordinator, uuid: str) -> None:
        super().__init__(coordinator)
        self._uuid = uuid
        self._attr_unique_id = f"{uuid}_step_counter"
        # The API doesn't report step counter state, so track locally.
        # Default to on (most users have it enabled).
        self._is_on = True

    @property
    def device_info(self) -> DeviceInfo:
        data = self.coordinator.get_device_data(self._uuid)
        return DeviceInfo(
            identifiers={(DOMAIN, self._uuid)},
            serial_number=data.get("serial_number"),
            name=data.get("name", self._uuid),
        )

    @property
    def is_on(self) -> bool:
        return self._is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable step counter."""
        success = await self.coordinator.api.send_command(
            self._uuid, CMD_STEP_COUNTER, ["1"]
        )
        if success:
            self._is_on = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable step counter."""
        success = await self.coordinator.api.send_command(
            self._uuid, CMD_STEP_COUNTER
        )
        if success:
            self._is_on = False
            self.async_write_ha_state()
