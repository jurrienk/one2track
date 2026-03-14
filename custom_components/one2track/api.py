"""One2Track API client.

Communicates with app.one2track.com / www.one2trackgps.com via session-based
authentication, HTML scraping for device state, and form POSTs for commands.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from aiohttp import ClientSession

from .const import BASE_URL, LOGIN_URL, SESSION_COOKIE

_LOGGER = logging.getLogger(__name__)


class AuthenticationError(Exception):
    """Raised when login fails or session expires."""


class One2TrackAPI:
    """Client for the One2Track web application."""

    def __init__(self, username: str, password: str, session: ClientSession) -> None:
        self._username = username
        self._password = password
        self._session = session
        self._cookie: str = ""
        self._csrf: str = ""
        self._account_id: str = ""
        self._device_uuids: list[str] = []

    @property
    def account_id(self) -> str:
        return self._account_id

    # ── Authentication ──────────────────────────────────────────────

    async def authenticate(self) -> str:
        """Full login flow. Returns account_id."""
        await self._fetch_csrf()
        await self._login()
        await self._discover_account_id()
        return self._account_id

    async def _fetch_csrf(self) -> None:
        """Get CSRF token and initial session cookie from login page."""
        resp = await self._session.get(
            LOGIN_URL,
            cookies={"accepted_cookies": "true"},
        )
        if resp.status != 200:
            raise AuthenticationError(f"Login page returned {resp.status}")
        html = await resp.text()
        self._csrf = self._parse_csrf(html)
        self._cookie = self._parse_cookie(resp)

    async def _login(self) -> None:
        """Submit login form."""
        data = {
            "authenticity_token": self._csrf,
            "user[login]": self._username,
            "user[password]": self._password,
            "gdpr": "1",
            "user[remember_me]": "1",
        }
        resp = await self._session.post(
            LOGIN_URL,
            data=data,
            headers={"content-type": "application/x-www-form-urlencoded"},
            cookies=self._cookies(),
            allow_redirects=False,
        )
        if resp.status == 302 and "Set-Cookie" in resp.headers:
            self._cookie = self._parse_cookie(resp)
            _LOGGER.debug("Login successful")
        else:
            raise AuthenticationError("Invalid username or password")

    async def _discover_account_id(self) -> None:
        """Follow redirect from base URL to discover account ID."""
        resp = await self._session.get(
            BASE_URL + "/",
            cookies=self._cookies(),
            allow_redirects=False,
        )
        if resp.status == 302 and "Location" in resp.headers:
            # Location: /users/<account_id>/devices
            parts = resp.headers["Location"].split("/")
            if len(parts) >= 3:
                self._account_id = parts[2]
                _LOGGER.debug("Discovered account ID: %s", self._account_id)
                return
        raise AuthenticationError("Could not discover account ID after login")

    async def _ensure_authenticated(self) -> None:
        """Re-authenticate if session is missing."""
        if not self._cookie:
            await self.authenticate()

    async def _refresh_csrf(self) -> str:
        """Get a fresh CSRF token from any page."""
        resp = await self._session.get(LOGIN_URL, cookies=self._cookies())
        if resp.status != 200:
            raise AuthenticationError("Could not refresh CSRF token")
        html = await resp.text()
        new_cookie = self._parse_cookie(resp)
        if new_cookie:
            self._cookie = new_cookie
        self._csrf = self._parse_csrf(html)
        return self._csrf

    # ── Device Discovery ────────────────────────────────────────────

    async def discover_devices(self) -> list[dict[str, Any]]:
        """Discover devices via JSON endpoint. Returns list of device dicts."""
        await self._ensure_authenticated()
        url = f"{BASE_URL}/users/{self._account_id}/devices"
        resp = await self._session.get(
            url,
            headers={
                "Accept": "application/json",
                "content-type": "application/json",
            },
            cookies=self._cookies(),
        )
        if resp.status != 200:
            self._cookie = ""
            raise AuthenticationError(f"Device list returned {resp.status}")

        data = await resp.json(content_type=None)
        devices = [item["device"] for item in data]
        self._device_uuids = [d["uuid"] for d in devices]
        _LOGGER.debug("Discovered %d devices", len(devices))
        return devices

    # ── Device State (HTML scraping) ────────────────────────────────

    async def get_device_state(self, uuid: str) -> dict[str, Any]:
        """Fetch rich device state by scraping the device HTML page.

        Returns a dict with 'device' and 'last_location' keys parsed from
        the inline JavaScript variables.
        """
        await self._ensure_authenticated()
        url = f"{BASE_URL}/devices/{uuid}"
        resp = await self._session.get(url, cookies=self._cookies())

        if resp.status != 200:
            if resp.status in (401, 302):
                self._cookie = ""
                raise AuthenticationError("Session expired")
            _LOGGER.error("Device page for %s returned %s", uuid, resp.status)
            return {}

        html = await resp.text()
        return self._parse_device_page(html, uuid)

    def _parse_device_page(self, html: str, uuid: str) -> dict[str, Any]:
        """Extract device and last_location from inline JS vars."""
        result: dict[str, Any] = {}

        device_match = re.search(r"var device\s*=\s*(\{.*?\})\s*;", html, re.DOTALL)
        if device_match:
            try:
                result["device"] = json.loads(device_match.group(1))
            except json.JSONDecodeError:
                _LOGGER.warning("Failed to parse device JSON for %s", uuid)

        location_match = re.search(
            r"var last_location\s*=\s*(\{.*?\})\s*;", html, re.DOTALL
        )
        if location_match:
            try:
                result["last_location"] = json.loads(location_match.group(1))
            except json.JSONDecodeError:
                _LOGGER.warning("Failed to parse last_location JSON for %s", uuid)

        return result

    async def get_all_device_states(self) -> dict[str, dict[str, Any]]:
        """Fetch state for all known devices. Returns {uuid: state_dict}."""
        await self._ensure_authenticated()

        if not self._device_uuids:
            devices = await self.discover_devices()
            self._device_uuids = [d["uuid"] for d in devices]

        states: dict[str, dict[str, Any]] = {}
        for uuid in self._device_uuids:
            try:
                state = await self.get_device_state(uuid)
                if state:
                    states[uuid] = state
            except AuthenticationError:
                # Session expired mid-loop, re-auth and retry this device
                await self.authenticate()
                state = await self.get_device_state(uuid)
                if state:
                    states[uuid] = state

        return states

    # ── Commands (settings & actions) ───────────────────────────────

    async def send_command(
        self, uuid: str, cmd_code: str, cmd_values: list[str] | None = None
    ) -> bool:
        """Send a command to a device.

        Uses PATCH /devices/{uuid}/functions with form-encoded data.
        cmd_values is a list of values sent as repeated function[cmd_value][] fields.
        """
        await self._ensure_authenticated()
        csrf = await self._refresh_csrf()

        url = f"{BASE_URL}/devices/{uuid}/functions"

        # Build form data as list of tuples to support repeated keys
        form_data: list[tuple[str, str]] = [
            ("utf8", "\u2713"),
            ("_method", "patch"),
            ("authenticity_token", csrf),
            ("function[cmd_code]", cmd_code),
        ]
        if cmd_values:
            for val in cmd_values:
                form_data.append(("function[cmd_value][]", val))

        resp = await self._session.post(
            url,
            data=form_data,
            headers={"content-type": "application/x-www-form-urlencoded"},
            cookies=self._cookies(),
        )
        success = resp.status == 200
        if not success:
            _LOGGER.error(
                "Command %s to %s failed with status %s", cmd_code, uuid, resp.status
            )
        return success

    # ── Messages ────────────────────────────────────────────────────

    async def send_message(self, uuid: str, message: str) -> bool:
        """Send a text message to a device."""
        await self._ensure_authenticated()
        csrf = await self._refresh_csrf()

        url = f"{BASE_URL}/devices/{uuid}/messages"
        data = {
            "utf8": "\u2713",
            "authenticity_token": csrf,
            "device_message[message]": message,
        }
        headers = {
            "x-csrf-token": csrf,
            "content-type": "application/x-www-form-urlencoded;charset=UTF-8",
            "accept": "text/vnd.turbo-stream.html, text/html, application/xhtml+xml",
        }
        resp = await self._session.post(
            url, data=data, headers=headers, cookies=self._cookies()
        )
        return resp.status == 200

    # ── Helpers ─────────────────────────────────────────────────────

    def _cookies(self) -> dict[str, str]:
        cookies = {"accepted_cookies": "true"}
        if self._cookie:
            cookies[SESSION_COOKIE] = self._cookie
        return cookies

    @staticmethod
    def _parse_csrf(html: str) -> str:
        match = re.search(r'name="csrf-token"\s+content="([^"]+)"', html)
        if match:
            return match.group(1)
        # Fallback: try authenticity_token hidden field
        match = re.search(r'name="authenticity_token"[^>]+value="([^"]+)"', html)
        if match:
            return match.group(1)
        raise AuthenticationError("CSRF token not found")

    @staticmethod
    def _parse_cookie(response) -> str:
        set_cookie = response.headers.get("Set-Cookie", "")
        if SESSION_COOKIE in set_cookie:
            # Extract cookie value: _iadmin=VALUE; path=...
            part = set_cookie.split(SESSION_COOKIE + "=")[1]
            return part.split(";")[0]
        return ""
