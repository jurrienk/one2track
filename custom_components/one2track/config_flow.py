"""Config flow for One2Track integration."""

from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .api import AuthenticationError, One2TrackAPI
from .const import CONF_ID, CONF_PASSWORD, CONF_USER_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)


class One2TrackConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for One2Track."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input:
            try:
                session = async_create_clientsession(self.hass)
                api = One2TrackAPI(
                    username=user_input[CONF_USER_NAME],
                    password=user_input[CONF_PASSWORD],
                    session=session,
                )
                account_id = await api.authenticate()
                # Verify we can discover devices
                await api.discover_devices()

                user_input[CONF_ID] = account_id
                await self.async_set_unique_id(account_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"One2Track ({user_input[CONF_USER_NAME]})",
                    data=user_input,
                )
            except AuthenticationError:
                errors["base"] = "authentication_error"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USER_NAME): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )
