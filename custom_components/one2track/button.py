"""Button platform for One2Track — action buttons."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CMD_FIND_DEVICE, CMD_REFRESH_LOCATION, DOMAIN
from .coordinator import One2TrackCoordinator


@dataclass(frozen=True, kw_only=True)
class One2TrackButtonDescription(ButtonEntityDescription):
    """Describes a One2Track action button."""
    cmd_code: str
    cmd_values: list[str] | None = None


BUTTON_DESCRIPTIONS: list[One2TrackButtonDescription] = [
    One2TrackButtonDescription(
        key="refresh_location",
        translation_key="refresh_location",
        icon="mdi:crosshairs-gps",
        cmd_code=CMD_REFRESH_LOCATION,
    ),
    One2TrackButtonDescription(
        key="find_device",
        translation_key="find_device",
        icon="mdi:bell-ring",
        cmd_code=CMD_FIND_DEVICE,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up One2Track action buttons."""
    coordinator: One2TrackCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    entities = []
    for device in coordinator.device_list:
        for desc in BUTTON_DESCRIPTIONS:
            entities.append(One2TrackButton(coordinator, device["uuid"], desc))

    async_add_entities(entities)


class One2TrackButton(CoordinatorEntity[One2TrackCoordinator], ButtonEntity):
    """An action button for a One2Track device."""

    entity_description: One2TrackButtonDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: One2TrackCoordinator,
        uuid: str,
        description: One2TrackButtonDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._uuid = uuid
        self._attr_unique_id = f"{uuid}_{description.key}"

    @property
    def device_info(self) -> DeviceInfo:
        data = self.coordinator.get_device_data(self._uuid)
        return DeviceInfo(
            identifiers={(DOMAIN, self._uuid)},
            serial_number=data.get("serial_number"),
            name=data.get("name", self._uuid),
        )

    async def async_press(self) -> None:
        """Handle button press — send the command."""
        desc = self.entity_description
        await self.coordinator.api.send_command(
            self._uuid, desc.cmd_code, desc.cmd_values
        )
        # Trigger a coordinator refresh after action
        await self.coordinator.async_request_refresh()
