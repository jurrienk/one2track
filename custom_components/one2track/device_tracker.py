"""Device tracker platform for One2Track."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.components.zone import async_active_zone
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import One2TrackCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up One2Track device trackers."""
    coordinator: One2TrackCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    async_add_entities(
        [
            One2TrackDeviceTracker(coordinator, hass, device)
            for device in coordinator.device_list
        ]
    )


class One2TrackDeviceTracker(CoordinatorEntity[One2TrackCoordinator], TrackerEntity):
    """A device tracker for a One2Track watch."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_icon = "mdi:watch-variant"

    def __init__(
        self,
        coordinator: One2TrackCoordinator,
        hass: HomeAssistant,
        device: dict[str, Any],
    ) -> None:
        super().__init__(coordinator)
        self._hass = hass
        self._uuid = device["uuid"]
        self._attr_unique_id = device["uuid"]

    @property
    def _data(self) -> dict[str, Any]:
        return self.coordinator.get_device_data(self._uuid)

    @property
    def _location(self) -> dict[str, Any]:
        return self._data.get("last_location", {})

    @property
    def device_info(self) -> DeviceInfo:
        data = self._data
        return DeviceInfo(
            identifiers={(DOMAIN, self._uuid)},
            serial_number=data.get("serial_number"),
            name=data.get("name", self._uuid),
        )

    @property
    def source_type(self) -> str:
        return "gps"

    @property
    def latitude(self) -> float | None:
        val = self._location.get("latitude")
        if val is not None:
            try:
                return float(val)
            except (ValueError, TypeError):
                return None
        return None

    @property
    def longitude(self) -> float | None:
        val = self._location.get("longitude")
        if val is not None:
            try:
                return float(val)
            except (ValueError, TypeError):
                return None
        return None

    @property
    def location_accuracy(self) -> float:
        meta = self._location.get("meta_data")
        if isinstance(meta, dict) and "accuracy_meters" in meta:
            return meta["accuracy_meters"]
        return 10

    @property
    def battery_level(self) -> int | None:
        return self._location.get("battery_percentage")

    @property
    def location_name(self) -> str | None:
        try:
            if self.latitude is not None and self.longitude is not None:
                zone = async_active_zone(
                    self._hass, self.latitude, self.longitude, self.location_accuracy
                )
                if zone:
                    return zone.name
        except Exception:
            pass
        return self._location.get("address")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self._data
        loc = self._location
        simcard = data.get("simcard", {})
        attrs = {
            "serial_number": data.get("serial_number"),
            "uuid": self._uuid,
            "status": data.get("status"),
            "phone_number": data.get("phone_number"),
            "location_type": loc.get("location_type"),
            "address": loc.get("address"),
            "altitude": loc.get("altitude"),
            "signal_strength": loc.get("signal_strength"),
            "satellite_count": loc.get("satellite_count"),
            "last_communication": loc.get("last_communication"),
            "last_location_update": loc.get("last_location_update"),
        }
        if simcard:
            attrs["tariff_type"] = simcard.get("tariff_type")
            attrs["balance_cents"] = simcard.get("balance_cents")
        return attrs
