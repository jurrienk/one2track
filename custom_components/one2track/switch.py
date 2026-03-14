"""Switch platform for One2Track — setting toggles."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchEntity

from .const import CMD_STEP_COUNTER
from .entity import One2TrackEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .data import One2TrackConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: One2TrackConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up One2Track setting switches."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        One2TrackStepCounterSwitch(coordinator, device["uuid"])
        for device in coordinator.device_list
    )


class One2TrackStepCounterSwitch(One2TrackEntity, SwitchEntity):
    """Switch to enable/disable the step counter on the watch."""

    _attr_translation_key = "step_counter"
    _attr_icon = "mdi:shoe-print"
    _attr_assumed_state = True

    def __init__(self, coordinator, uuid: str) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, uuid)
        self._attr_unique_id = f"{uuid}_step_counter"
        self._is_on = True

    @property
    def is_on(self) -> bool:
        """Return True if step counter is enabled."""
        return self._is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable step counter."""
        success = await self.coordinator.client.async_send_command(
            self._uuid, CMD_STEP_COUNTER, ["1"]
        )
        if success:
            self._is_on = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable step counter."""
        success = await self.coordinator.client.async_send_command(
            self._uuid, CMD_STEP_COUNTER
        )
        if success:
            self._is_on = False
            self.async_write_ha_state()
