"""Binary sensor platform for One2Track."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import One2TrackCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up One2Track binary sensor entities."""
    coordinator: One2TrackCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    async_add_entities(
        [One2TrackTumbleSensor(coordinator, device["uuid"]) for device in coordinator.device_list]
    )


class One2TrackTumbleSensor(CoordinatorEntity[One2TrackCoordinator], BinarySensorEntity):
    """Binary sensor for fall detection."""

    _attr_has_entity_name = True
    _attr_translation_key = "tumble"
    _attr_device_class = BinarySensorDeviceClass.SAFETY

    def __init__(self, coordinator: One2TrackCoordinator, uuid: str) -> None:
        super().__init__(coordinator)
        self._uuid = uuid
        self._attr_unique_id = f"{uuid}_tumble"

    @property
    def device_info(self) -> DeviceInfo:
        data = self.coordinator.get_device_data(self._uuid)
        return DeviceInfo(
            identifiers={(DOMAIN, self._uuid)},
            serial_number=data.get("serial_number"),
            name=data.get("name", self._uuid),
        )

    @property
    def is_on(self) -> bool | None:
        data = self.coordinator.get_device_data(self._uuid)
        loc = data.get("last_location", {})
        meta = loc.get("meta_data")
        if isinstance(meta, dict):
            return meta.get("tumble") == "1"
        return None
