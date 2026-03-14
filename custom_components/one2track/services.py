"""Service handlers for One2Track."""

from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .api import One2TrackAPI
from .const import (
    CMD_ALARMS,
    CMD_CHANGE_PASSWORD,
    CMD_FACTORY_RESET,
    CMD_FIND_DEVICE,
    CMD_INTERCOM,
    CMD_LANGUAGE_TIMEZONE,
    CMD_PHONEBOOK,
    CMD_QUIET_TIMES,
    CMD_REFRESH_LOCATION,
    CMD_REMOTE_SHUTDOWN,
    CMD_SOS_NUMBER,
    CMD_WHITELIST_1,
    CMD_WHITELIST_2,
    DOMAIN,
)
from .coordinator import One2TrackCoordinator

_LOGGER = logging.getLogger(__name__)

# ── Action services (perform an action on the watch) ──────────────
SERVICE_SEND_MESSAGE = "send_message"
SERVICE_FORCE_UPDATE = "force_update"
SERVICE_FIND_DEVICE = "find_device"
SERVICE_INTERCOM = "intercom"

# ── Setting services (change a watch setting) ─────────────────────
SERVICE_SEND_DEVICE_COMMAND = "send_device_command"
SERVICE_SET_SOS_NUMBER = "set_sos_number"
SERVICE_SET_ALARMS = "set_alarms"
SERVICE_SET_PHONEBOOK = "set_phonebook"
SERVICE_SET_WHITELIST = "set_whitelist"
SERVICE_SET_QUIET_TIMES = "set_quiet_times"
SERVICE_SET_LANGUAGE_TIMEZONE = "set_language_timezone"
SERVICE_CHANGE_PASSWORD = "change_password"
SERVICE_FACTORY_RESET = "factory_reset"
SERVICE_REMOTE_SHUTDOWN = "remote_shutdown"


def _resolve_device_uuid(hass: HomeAssistant, entity_ids: list[str]) -> str:
    """Resolve a target entity ID to a One2Track device UUID."""
    if not entity_ids:
        raise HomeAssistantError("No target entity specified")

    registry = er.async_get(hass)

    for entity_id in entity_ids:
        entry = registry.async_get(entity_id)
        if entry and entry.platform == DOMAIN:
            unique_id = entry.unique_id
            # unique_id is either the UUID itself (device_tracker) or UUID_suffix (sensors etc)
            for entry_data in hass.data.get(DOMAIN, {}).values():
                if not isinstance(entry_data, dict):
                    continue
                coordinator: One2TrackCoordinator | None = entry_data.get("coordinator")
                if coordinator:
                    for device in coordinator.device_list:
                        dev_uuid = device.get("uuid", "")
                        if unique_id == dev_uuid or unique_id.startswith(dev_uuid + "_"):
                            return dev_uuid
            return unique_id

    raise HomeAssistantError(f"Could not resolve One2Track device from {entity_ids}")


def _get_api_for_uuid(hass: HomeAssistant, device_uuid: str) -> One2TrackAPI:
    """Find the API client that manages a given device UUID."""
    for entry_data in hass.data.get(DOMAIN, {}).values():
        if not isinstance(entry_data, dict):
            continue
        coordinator: One2TrackCoordinator | None = entry_data.get("coordinator")
        if coordinator:
            for device in coordinator.device_list:
                if device.get("uuid") == device_uuid:
                    return entry_data["api"]

    raise HomeAssistantError(f"No One2Track client found for device {device_uuid}")


def _get_coordinator_for_uuid(hass: HomeAssistant, device_uuid: str) -> One2TrackCoordinator:
    """Find the coordinator that manages a given device UUID."""
    for entry_data in hass.data.get(DOMAIN, {}).values():
        if not isinstance(entry_data, dict):
            continue
        coordinator: One2TrackCoordinator | None = entry_data.get("coordinator")
        if coordinator:
            for device in coordinator.device_list:
                if device.get("uuid") == device_uuid:
                    return coordinator

    raise HomeAssistantError(f"No coordinator found for device {device_uuid}")


def _extract_entity_ids(call: ServiceCall) -> list[str]:
    entity_ids = call.data.get("entity_id", [])
    if isinstance(entity_ids, str):
        entity_ids = [entity_ids]
    return entity_ids


async def async_setup_services(hass: HomeAssistant) -> None:
    """Register One2Track services."""
    if hass.services.has_service(DOMAIN, SERVICE_SEND_MESSAGE):
        return

    # ── Action: Send message ──────────────────────────────────────

    async def handle_send_message(call: ServiceCall) -> None:
        entity_ids = _extract_entity_ids(call)
        uuid = _resolve_device_uuid(hass, entity_ids)
        api = _get_api_for_uuid(hass, uuid)
        message = call.data["message"]
        _LOGGER.info("Sending message to %s: %s", uuid, message)
        if not await api.send_message(uuid, message):
            raise HomeAssistantError("Failed to send message")

    # ── Action: Force update (refresh location) ───────────────────

    async def handle_force_update(call: ServiceCall) -> None:
        entity_ids = _extract_entity_ids(call)
        uuid = _resolve_device_uuid(hass, entity_ids)
        api = _get_api_for_uuid(hass, uuid)
        _LOGGER.info("Requesting location refresh for %s", uuid)
        if not await api.send_command(uuid, CMD_REFRESH_LOCATION):
            raise HomeAssistantError("Failed to activate positioning mode")
        coordinator = _get_coordinator_for_uuid(hass, uuid)
        await coordinator.async_request_refresh()

    # ── Action: Find device (ring the watch) ────────────────────

    async def handle_find_device(call: ServiceCall) -> None:
        entity_ids = _extract_entity_ids(call)
        uuid = _resolve_device_uuid(hass, entity_ids)
        api = _get_api_for_uuid(hass, uuid)
        _LOGGER.info("Ringing device %s", uuid)
        if not await api.send_command(uuid, CMD_FIND_DEVICE):
            raise HomeAssistantError("Failed to ring device")

    # ── Action: Intercom (make watch call a number) ───────────────

    async def handle_intercom(call: ServiceCall) -> None:
        entity_ids = _extract_entity_ids(call)
        uuid = _resolve_device_uuid(hass, entity_ids)
        api = _get_api_for_uuid(hass, uuid)
        phone = call.data["phone_number"]
        _LOGGER.info("Initiating intercom call from %s to %s", uuid, phone)
        if not await api.send_command(uuid, CMD_INTERCOM, [phone]):
            raise HomeAssistantError("Failed to initiate intercom call")

    # ── Setting: Send device command (generic) ────────────────────

    async def handle_send_device_command(call: ServiceCall) -> None:
        entity_ids = _extract_entity_ids(call)
        uuid = _resolve_device_uuid(hass, entity_ids)
        api = _get_api_for_uuid(hass, uuid)
        cmd_code = call.data["cmd_code"]
        cmd_values = call.data.get("cmd_values", [])
        _LOGGER.info("Sending command %s to %s", cmd_code, uuid)
        if not await api.send_command(uuid, cmd_code, cmd_values or None):
            raise HomeAssistantError(f"Failed to send command {cmd_code}")

    # ── Setting: SOS number ───────────────────────────────────────

    async def handle_set_sos_number(call: ServiceCall) -> None:
        entity_ids = _extract_entity_ids(call)
        uuid = _resolve_device_uuid(hass, entity_ids)
        api = _get_api_for_uuid(hass, uuid)
        phone = call.data["phone_number"]
        if not await api.send_command(uuid, CMD_SOS_NUMBER, [phone]):
            raise HomeAssistantError("Failed to set SOS number")

    # ── Setting: Alarms ───────────────────────────────────────────

    async def handle_set_alarms(call: ServiceCall) -> None:
        entity_ids = _extract_entity_ids(call)
        uuid = _resolve_device_uuid(hass, entity_ids)
        api = _get_api_for_uuid(hass, uuid)
        alarms = call.data.get("alarms", [])
        if not await api.send_command(uuid, CMD_ALARMS, alarms or None):
            raise HomeAssistantError("Failed to set alarms")

    # ── Setting: Phonebook ────────────────────────────────────────

    async def handle_set_phonebook(call: ServiceCall) -> None:
        entity_ids = _extract_entity_ids(call)
        uuid = _resolve_device_uuid(hass, entity_ids)
        api = _get_api_for_uuid(hass, uuid)
        contacts = call.data.get("contacts", [])
        # Contacts are sent as alternating name/number pairs
        values = []
        for contact in contacts:
            values.append(contact["name"])
            values.append(contact["number"])
        if not await api.send_command(uuid, CMD_PHONEBOOK, values or None):
            raise HomeAssistantError("Failed to set phonebook")

    # ── Setting: Whitelist ────────────────────────────────────────

    async def handle_set_whitelist(call: ServiceCall) -> None:
        entity_ids = _extract_entity_ids(call)
        uuid = _resolve_device_uuid(hass, entity_ids)
        api = _get_api_for_uuid(hass, uuid)
        numbers = call.data.get("phone_numbers", [])
        # Pad to 10 entries, split into two groups of 5
        padded = (numbers + [""] * 10)[:10]
        list1 = padded[:5]
        list2 = padded[5:]
        if not await api.send_command(uuid, CMD_WHITELIST_1, list1):
            raise HomeAssistantError("Failed to set whitelist (slots 1-5)")
        if not await api.send_command(uuid, CMD_WHITELIST_2, list2):
            raise HomeAssistantError("Failed to set whitelist (slots 6-10)")

    # ── Setting: Quiet times ──────────────────────────────────────

    async def handle_set_quiet_times(call: ServiceCall) -> None:
        entity_ids = _extract_entity_ids(call)
        uuid = _resolve_device_uuid(hass, entity_ids)
        api = _get_api_for_uuid(hass, uuid)
        windows = call.data.get("windows", [])
        values = []
        for i, window in enumerate(windows):
            start = window["start"].replace(":", "")
            end = window["end"].replace(":", "")
            is_last = i == len(windows) - 1
            entry = f"1,{start},{end},1"
            if is_last:
                entry += ",1"
            values.append(entry)
        if not await api.send_command(uuid, CMD_QUIET_TIMES, values or None):
            raise HomeAssistantError("Failed to set quiet times")

    # ── Setting: Language & timezone ──────────────────────────────

    async def handle_set_language_timezone(call: ServiceCall) -> None:
        entity_ids = _extract_entity_ids(call)
        uuid = _resolve_device_uuid(hass, entity_ids)
        api = _get_api_for_uuid(hass, uuid)
        language = str(call.data["language"])
        utc_offset = str(call.data["utc_offset"])
        if not await api.send_command(uuid, CMD_LANGUAGE_TIMEZONE, [language, utc_offset]):
            raise HomeAssistantError("Failed to set language/timezone")

    # ── Setting: Change password ──────────────────────────────────

    async def handle_change_password(call: ServiceCall) -> None:
        entity_ids = _extract_entity_ids(call)
        uuid = _resolve_device_uuid(hass, entity_ids)
        api = _get_api_for_uuid(hass, uuid)
        password = call.data["password"]
        _LOGGER.warning("Changing password for device %s", uuid)
        if not await api.send_command(uuid, CMD_CHANGE_PASSWORD, [password]):
            raise HomeAssistantError("Failed to change password")

    # ── Dangerous: Factory reset ──────────────────────────────────

    async def handle_factory_reset(call: ServiceCall) -> None:
        entity_ids = _extract_entity_ids(call)
        uuid = _resolve_device_uuid(hass, entity_ids)
        api = _get_api_for_uuid(hass, uuid)
        _LOGGER.warning("Factory resetting device %s — this cannot be undone!", uuid)
        if not await api.send_command(uuid, CMD_FACTORY_RESET):
            raise HomeAssistantError("Failed to send factory reset")

    # ── Dangerous: Remote shutdown ────────────────────────────────

    async def handle_remote_shutdown(call: ServiceCall) -> None:
        entity_ids = _extract_entity_ids(call)
        uuid = _resolve_device_uuid(hass, entity_ids)
        api = _get_api_for_uuid(hass, uuid)
        _LOGGER.warning("Remotely shutting down device %s — cannot be re-enabled remotely!", uuid)
        if not await api.send_command(uuid, CMD_REMOTE_SHUTDOWN):
            raise HomeAssistantError("Failed to send remote shutdown")

    # ── Register all services ─────────────────────────────────────

    # Actions
    hass.services.async_register(
        DOMAIN, SERVICE_SEND_MESSAGE, handle_send_message,
        schema=vol.Schema({
            vol.Required("entity_id"): vol.Any(str, [str]),
            vol.Required("message"): str,
        }),
    )
    hass.services.async_register(
        DOMAIN, SERVICE_FORCE_UPDATE, handle_force_update,
        schema=vol.Schema({
            vol.Required("entity_id"): vol.Any(str, [str]),
        }),
    )
    hass.services.async_register(
        DOMAIN, SERVICE_FIND_DEVICE, handle_find_device,
        schema=vol.Schema({
            vol.Required("entity_id"): vol.Any(str, [str]),
        }),
    )
    hass.services.async_register(
        DOMAIN, SERVICE_INTERCOM, handle_intercom,
        schema=vol.Schema({
            vol.Required("entity_id"): vol.Any(str, [str]),
            vol.Required("phone_number"): str,
        }),
    )

    # Settings
    hass.services.async_register(
        DOMAIN, SERVICE_SEND_DEVICE_COMMAND, handle_send_device_command,
        schema=vol.Schema({
            vol.Required("entity_id"): vol.Any(str, [str]),
            vol.Required("cmd_code"): str,
            vol.Optional("cmd_values", default=[]): vol.All(
                vol.Any(str, [str]),
                lambda v: [v] if isinstance(v, str) else v,
            ),
        }),
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_SOS_NUMBER, handle_set_sos_number,
        schema=vol.Schema({
            vol.Required("entity_id"): vol.Any(str, [str]),
            vol.Required("phone_number"): str,
        }),
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_ALARMS, handle_set_alarms,
        schema=vol.Schema({
            vol.Required("entity_id"): vol.Any(str, [str]),
            vol.Optional("alarms", default=[]): [str],
        }),
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_PHONEBOOK, handle_set_phonebook,
        schema=vol.Schema({
            vol.Required("entity_id"): vol.Any(str, [str]),
            vol.Optional("contacts", default=[]): [
                vol.Schema({
                    vol.Required("name"): str,
                    vol.Required("number"): str,
                })
            ],
        }),
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_WHITELIST, handle_set_whitelist,
        schema=vol.Schema({
            vol.Required("entity_id"): vol.Any(str, [str]),
            vol.Required("phone_numbers"): [str],
        }),
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_QUIET_TIMES, handle_set_quiet_times,
        schema=vol.Schema({
            vol.Required("entity_id"): vol.Any(str, [str]),
            vol.Optional("windows", default=[]): [
                vol.Schema({
                    vol.Required("start"): str,
                    vol.Required("end"): str,
                })
            ],
        }),
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_LANGUAGE_TIMEZONE, handle_set_language_timezone,
        schema=vol.Schema({
            vol.Required("entity_id"): vol.Any(str, [str]),
            vol.Required("language"): vol.In(["1", "5", "16"]),
            vol.Required("utc_offset"): str,
        }),
    )
    hass.services.async_register(
        DOMAIN, SERVICE_CHANGE_PASSWORD, handle_change_password,
        schema=vol.Schema({
            vol.Required("entity_id"): vol.Any(str, [str]),
            vol.Required("password"): vol.All(str, vol.Length(min=6, max=6)),
        }),
    )
    hass.services.async_register(
        DOMAIN, SERVICE_FACTORY_RESET, handle_factory_reset,
        schema=vol.Schema({
            vol.Required("entity_id"): vol.Any(str, [str]),
        }),
    )
    hass.services.async_register(
        DOMAIN, SERVICE_REMOTE_SHUTDOWN, handle_remote_shutdown,
        schema=vol.Schema({
            vol.Required("entity_id"): vol.Any(str, [str]),
        }),
    )


async def async_unload_services(hass: HomeAssistant) -> None:
    """Unload One2Track services."""
    for service in (
        SERVICE_SEND_MESSAGE,
        SERVICE_FORCE_UPDATE,
        SERVICE_FIND_DEVICE,
        SERVICE_INTERCOM,
        SERVICE_SEND_DEVICE_COMMAND,
        SERVICE_SET_SOS_NUMBER,
        SERVICE_SET_ALARMS,
        SERVICE_SET_PHONEBOOK,
        SERVICE_SET_WHITELIST,
        SERVICE_SET_QUIET_TIMES,
        SERVICE_SET_LANGUAGE_TIMEZONE,
        SERVICE_CHANGE_PASSWORD,
        SERVICE_FACTORY_RESET,
        SERVICE_REMOTE_SHUTDOWN,
    ):
        hass.services.async_remove(DOMAIN, service)
