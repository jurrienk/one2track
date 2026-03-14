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
from .const import DEFAULT_UPDATE_INTERVAL_SECONDS, LOGGER, RADIO_COMMANDS

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .api import One2TrackApiClient
    from .data import One2TrackConfigEntry


class One2TrackCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Coordinator that polls device state from One2Track.

    Data structure: {uuid: {"device": {...}, "last_location": {...}}}
    The initial device list (from JSON endpoint) is stored separately for
    discovery metadata (serial_number, name, simcard, etc.).
    Per-device capabilities (supported commands and options) are discovered
    at setup and stored for entity creation.
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
        # Per-device capabilities: {uuid: {"functions": {...}, "options": {...}}}
        self._capabilities: dict[str, dict[str, Any]] = {}

    @property
    def device_list(self) -> list[dict[str, Any]]:
        """Return the initial device list (from JSON discovery)."""
        return self._device_list

    def get_capabilities(self, uuid: str) -> dict[str, Any]:
        """Return discovered capabilities for a device.

        Returns {"functions": {code: label, ...}, "options": {code: [...], ...}}
        """
        return self._capabilities.get(uuid, {"functions": {}, "options": {}})

    def device_supports(self, uuid: str, cmd_code: str) -> bool:
        """Check if a device supports a given command code."""
        caps = self.get_capabilities(uuid)
        return cmd_code in caps.get("functions", {})

    def device_find_code(self, uuid: str, candidates: tuple[str, ...]) -> str | None:
        """Find which of several candidate command codes this device supports.

        Used for model-specific commands (GPS interval: 0077 or 0078, etc.)
        Returns the first matching code, or None.
        """
        caps = self.get_capabilities(uuid)
        funcs = caps.get("functions", {})
        for code in candidates:
            if code in funcs:
                return code
        return None

    def get_command_options(self, uuid: str, cmd_code: str) -> list[dict[str, Any]]:
        """Return discovered options for a command on a device."""
        caps = self.get_capabilities(uuid)
        return caps.get("options", {}).get(cmd_code, [])

    async def async_setup(self) -> None:
        """Discover devices and their capabilities during initial setup."""
        self._device_list = await self.client.async_discover_devices()

        # Discover capabilities for each device
        for dev in self._device_list:
            uuid = dev.get("uuid", "")
            if not uuid:
                continue
            try:
                caps = await self.client.async_discover_capabilities(uuid)

                # For commands with radio-button options, discover the options
                functions = caps.get("functions", {})
                options: dict[str, list] = {}
                for code in RADIO_COMMANDS:
                    if code in functions:
                        opts = await self.client.async_discover_command_options(
                            uuid, code
                        )
                        if opts:
                            options[code] = opts
                caps["options"] = options

                self._capabilities[uuid] = caps
                LOGGER.info(
                    "Device %s (%s): %d commands, options for %s",
                    dev.get("name", uuid),
                    uuid,
                    len(functions),
                    list(options.keys()),
                )
            except One2TrackApiClientError as exc:
                LOGGER.warning(
                    "Could not discover capabilities for %s: %s", uuid, exc
                )
                self._capabilities[uuid] = {"functions": {}, "options": {}}

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
