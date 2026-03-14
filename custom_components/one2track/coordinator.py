"""DataUpdateCoordinator for One2Track."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from aiohttp import ClientError
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import AuthenticationError, One2TrackAPI
from .const import DEFAULT_UPDATE_INTERVAL_SECONDS

_LOGGER = logging.getLogger(__name__)


class One2TrackCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Coordinator that polls device state from One2Track.

    Data structure: {uuid: {"device": {...}, "last_location": {...}}}
    The initial device list (from JSON endpoint) is stored separately for
    discovery metadata (serial_number, name, simcard, etc.).
    """

    def __init__(self, hass: HomeAssistant, api: One2TrackAPI) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="One2Track",
            update_interval=timedelta(seconds=DEFAULT_UPDATE_INTERVAL_SECONDS),
            always_update=False,
        )
        self.api = api
        self._device_list: list[dict[str, Any]] = []

    @property
    def device_list(self) -> list[dict[str, Any]]:
        """Return the initial device list (from JSON discovery)."""
        return self._device_list

    async def async_setup(self) -> None:
        """Discover devices during initial setup."""
        self._device_list = await self.api.discover_devices()

    def get_device_data(self, uuid: str) -> dict[str, Any]:
        """Get merged device data for a UUID.

        Merges the initial JSON discovery data with the scraped HTML data.
        The HTML-scraped data takes precedence for overlapping fields.
        """
        # Start with JSON discovery data as base
        base: dict[str, Any] = {}
        for dev in self._device_list:
            if dev.get("uuid") == uuid:
                base = dict(dev)
                break

        # Overlay HTML-scraped data
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
                states = await self.api.get_all_device_states()
                _LOGGER.debug("Updated %d devices", len(states))
                return states
        except (ClientError, AuthenticationError, TimeoutError) as err:
            _LOGGER.error("Error updating from One2Track: %s", err)
            raise UpdateFailed(f"Error communicating with One2Track: {err}") from err
