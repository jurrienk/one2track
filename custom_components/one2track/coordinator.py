"""DataUpdateCoordinator for the One2Track integration."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    One2TrackApiClientAuthenticationError,
    One2TrackApiClientError,
)
from .const import DEFAULT_UPDATE_INTERVAL_SECONDS, LOGGER

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .api import One2TrackApiClient
    from .data import One2TrackConfigEntry


class One2TrackCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Coordinator that polls device state from One2Track.

    Data structure: {uuid: {"device": {...}, "last_location": {...}}}
    The initial device list (from JSON endpoint) is stored separately for
    discovery metadata (serial_number, name, simcard, etc.).
    """

    config_entry: One2TrackConfigEntry

    def __init__(self, hass: HomeAssistant, client: One2TrackApiClient) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name="One2Track",
            update_interval=timedelta(seconds=DEFAULT_UPDATE_INTERVAL_SECONDS),
            always_update=False,
        )
        self.client = client
        self._device_list: list[dict[str, Any]] = []

    @property
    def device_list(self) -> list[dict[str, Any]]:
        """Return the initial device list (from JSON discovery)."""
        return self._device_list

    async def async_setup(self) -> None:
        """Discover devices during initial setup."""
        self._device_list = await self.client.async_discover_devices()

    def get_device_data(self, uuid: str) -> dict[str, Any]:
        """Get merged device data for a UUID.

        Merges the initial JSON discovery data with the scraped HTML data.
        The HTML-scraped data takes precedence for overlapping fields.
        """
        base: dict[str, Any] = {}
        for dev in self._device_list:
            if dev.get("uuid") == uuid:
                base = dict(dev)
                break

        if self.data and uuid in self.data:
            scraped = self.data[uuid]
            if "device" in scraped:
                base.update(scraped["device"])
            if "last_location" in scraped:
                base["last_location"] = scraped["last_location"]

        return base

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        """Fetch device states from One2Track."""
        try:
            async with asyncio.timeout(60):
                return await self.client.async_get_all_device_states()
        except One2TrackApiClientAuthenticationError as exc:
            raise ConfigEntryAuthFailed(exc) from exc
        except One2TrackApiClientError as exc:
            raise UpdateFailed(exc) from exc
