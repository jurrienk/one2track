"""Select platform for One2Track — setting selectors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.components.select import SelectEntity, SelectEntityDescription

from .const import (
    CMD_GPS_INTERVAL,
    CMD_PROFILE_MODE,
    GPS_INTERVAL_OPTIONS,
    PROFILE_MODE_OPTIONS,
)
from .entity import One2TrackEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import One2TrackCoordinator
    from .data import One2TrackConfigEntry


@dataclass(frozen=True, kw_only=True)
class One2TrackSelectDescription(SelectEntityDescription):
    """Describes a One2Track select entity."""

    cmd_code: str
    value_map: dict[str, str]  # {api_value: display_label}


SELECT_DESCRIPTIONS: tuple[One2TrackSelectDescription, ...] = (
    One2TrackSelectDescription(
        key="gps_interval",
        translation_key="gps_interval",
        icon="mdi:map-marker-distance",
        cmd_code=CMD_GPS_INTERVAL,
        value_map=GPS_INTERVAL_OPTIONS,
    ),
    One2TrackSelectDescription(
        key="profile_mode",
        translation_key="profile_mode",
        icon="mdi:bell-cog",
        cmd_code=CMD_PROFILE_MODE,
        value_map=PROFILE_MODE_OPTIONS,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: One2TrackConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up One2Track setting selects."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        One2TrackSelect(coordinator, device["uuid"], desc)
        for device in coordinator.device_list
        for desc in SELECT_DESCRIPTIONS
    )


class One2TrackSelect(One2TrackEntity, SelectEntity):
    """A select entity for a One2Track device setting."""

    entity_description: One2TrackSelectDescription

    def __init__(
        self,
        coordinator: One2TrackCoordinator,
        uuid: str,
        description: One2TrackSelectDescription,
    ) -> None:
        """Initialize the select."""
        super().__init__(coordinator, uuid)
        self.entity_description = description
        self._attr_unique_id = f"{uuid}_{description.key}"
        self._label_to_value = {v: k for k, v in description.value_map.items()}
        self._attr_options = list(description.value_map.values())
        self._attr_current_option = self._attr_options[0]

    async def async_select_option(self, option: str) -> None:
        """Send the selected setting to the watch."""
        api_value = self._label_to_value.get(option)
        if api_value is None:
            return
        success = await self.coordinator.client.async_send_command(
            self._uuid, self.entity_description.cmd_code, [api_value]
        )
        if success:
            self._attr_current_option = option
            self.async_write_ha_state()
