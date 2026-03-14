"""Select platform for One2Track — setting selectors."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CMD_GPS_INTERVAL,
    CMD_PROFILE_MODE,
    DOMAIN,
    GPS_INTERVAL_OPTIONS,
    PROFILE_MODE_OPTIONS,
)
from .coordinator import One2TrackCoordinator


@dataclass(frozen=True, kw_only=True)
class One2TrackSelectDescription(SelectEntityDescription):
    """Describes a One2Track select entity."""
    cmd_code: str
    value_map: dict[str, str]  # {api_value: display_label}


SELECT_DESCRIPTIONS: list[One2TrackSelectDescription] = [
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
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up One2Track setting selects."""
    coordinator: One2TrackCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    entities = []
    for device in coordinator.device_list:
        for desc in SELECT_DESCRIPTIONS:
            entities.append(One2TrackSelect(coordinator, device["uuid"], desc))

    async_add_entities(entities)


class One2TrackSelect(CoordinatorEntity[One2TrackCoordinator], SelectEntity):
    """A select entity for a One2Track device setting."""

    entity_description: One2TrackSelectDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: One2TrackCoordinator,
        uuid: str,
        description: One2TrackSelectDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._uuid = uuid
        self._attr_unique_id = f"{uuid}_{description.key}"
        self._label_to_value = {v: k for k, v in description.value_map.items()}
        self._attr_options = list(description.value_map.values())
        # Default to first option; API doesn't report current setting
        self._attr_current_option = self._attr_options[0]

    @property
    def device_info(self) -> DeviceInfo:
        data = self.coordinator.get_device_data(self._uuid)
        return DeviceInfo(
            identifiers={(DOMAIN, self._uuid)},
            serial_number=data.get("serial_number"),
            name=data.get("name", self._uuid),
        )

    async def async_select_option(self, option: str) -> None:
        """Send the selected setting to the watch."""
        api_value = self._label_to_value.get(option)
        if api_value is None:
            return
        success = await self.coordinator.api.send_command(
            self._uuid, self.entity_description.cmd_code, [api_value]
        )
        if success:
            self._attr_current_option = option
            self.async_write_ha_state()
