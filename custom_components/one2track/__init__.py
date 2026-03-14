"""The One2Track integration."""

from __future__ import annotations

from aiohttp import ClientError
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .api import AuthenticationError, One2TrackAPI
from .const import CONF_ID, CONF_PASSWORD, CONF_USER_NAME, DOMAIN, LOGGER
from .coordinator import One2TrackCoordinator
from .services import async_setup_services, async_unload_services

PLATFORMS = [
    Platform.DEVICE_TRACKER,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SWITCH,
    Platform.SELECT,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up One2Track from a config entry."""
    session = async_create_clientsession(hass)
    api = One2TrackAPI(
        username=entry.data[CONF_USER_NAME],
        password=entry.data[CONF_PASSWORD],
        session=session,
    )

    try:
        account_id = await api.authenticate()
    except (ClientError, AuthenticationError) as ex:
        LOGGER.error("Could not authenticate with One2Track")
        raise ConfigEntryNotReady from ex

    coordinator = One2TrackCoordinator(hass, api)

    try:
        await coordinator.async_setup()
    except (ClientError, AuthenticationError) as ex:
        LOGGER.error("Could not discover One2Track devices")
        raise ConfigEntryNotReady from ex

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "coordinator": coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await async_setup_services(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.data[DOMAIN]:
            await async_unload_services(hass)

    return unload_ok
