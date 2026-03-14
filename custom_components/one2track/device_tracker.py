"""Device tracker platform for One2Track."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.components.zone import async_active_zone

from .const import DOMAIN
from .entity import One2TrackEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .data import One2TrackConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: One2TrackConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up One2Track device trackers."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        One2TrackDeviceTracker(coordinator, hass, device["uuid"])
        for device in coordinator.device_list
    )


class One2TrackDeviceTracker(One2TrackEntity, TrackerEntity):
    """A device tracker for a One2Track watch."""

    _attr_name = None
    _attr_icon = "mdi:watch-variant"

    def __init__(self, coordinator, hass, uuid: str) -> None:
        """Initialize the tracker."""
        super().__init__(coordinator, uuid)
        self._hass = hass
        self._attr_unique_id = uuid

    @property
    def source_type(self) -> str:
        """Return the source type."""
        return "gps"

    @property
    def latitude(self) -> float | None:
        """Return latitude."""
        val = self._location.get("latitude")
        if val is not None:
            try:
                return float(val)
            except (ValueError, TypeError):
                return None
        return None

    @property
    def longitude(self) -> float | None:
        """Return longitude."""
        val = self._location.get("longitude")
        if val is not None:
            try:
                return float(val)
            except (ValueError, TypeError):
                return None
        return None

    @property
    def location_accuracy(self) -> float:
        """Return the GPS accuracy in meters."""
        meta = self._location.get("meta_data")
        if isinstance(meta, dict) and "accuracy_meters" in meta:
            return meta["accuracy_meters"]
        return 10

    @property
    def battery_level(self) -> int | None:
        """Return battery level."""
        return self._location.get("battery_percentage")

    @property
    def location_name(self) -> str | None:
        """Return location name (zone or address)."""
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
        """Return device-specific attributes."""
        data = self._data
        loc = self._location
        simcard = data.get("simcard", {})
        attrs: dict[str, Any] = {
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
