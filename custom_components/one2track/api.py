"""One2Track API client.

Communicates with www.one2trackgps.com via session-based authentication,
HTML scraping for device state, and form POSTs for commands.
"""

from __future__ import annotations

import json
import re
import socket
from typing import Any
from urllib.parse import urlparse

import aiohttp
import async_timeout

from .const import BASE_URL, LOGIN_URL, SESSION_COOKIE


class One2TrackApiClientError(Exception):
    """Base exception for One2Track API errors."""


class One2TrackApiClientCommunicationError(One2TrackApiClientError):
    """Exception for network/communication errors."""


class One2TrackApiClientAuthenticationError(One2TrackApiClientError):
    """Exception for authentication failures."""


class One2TrackApiClient:
    """Client for the One2Track web application."""

    def __init__(
        self,
        username: str,
        password: str,
        session: aiohttp.ClientSession,
    ) -> None:
        """Initialize the API client."""
        self._username = username
        self._password = password
        self._session = session
        self._cookie: str = ""
        self._csrf: str = ""
        self._account_id: str = ""
        self._device_uuids: list[str] = []

    @property
    def account_id(self) -> str:
        """Return the discovered account ID."""
        return self._account_id

    # ── Authentication ──────────────────────────────────────────────

    async def async_authenticate(self) -> str:
        """Full login flow. Returns account_id.

        Raises:
            One2TrackApiClientAuthenticationError: If credentials are invalid.
            One2TrackApiClientCommunicationError: If network errors occur.
        """
        await self._async_fetch_csrf()
        await self._async_login()
        await self._async_discover_account_id()
        return self._account_id

    async def _async_fetch_csrf(self) -> None:
        """Get CSRF token and initial session cookie from login page."""
        try:
            async with async_timeout.timeout(10):
                resp = await self._session.get(
                    LOGIN_URL,
                    cookies={"accepted_cookies": "true"},
                )
        except TimeoutError as exc:
            raise One2TrackApiClientCommunicationError(
                "Timeout fetching login page"
            ) from exc
        except (aiohttp.ClientError, socket.gaierror) as exc:
            raise One2TrackApiClientCommunicationError(
                f"Error fetching login page: {exc}"
            ) from exc

        if resp.status != 200:
            raise One2TrackApiClientCommunicationError(
                f"Login page returned {resp.status}"
            )
        html = await resp.text()
        self._csrf = self._parse_csrf(html)
        self._cookie = self._parse_cookie(resp)

    async def _async_login(self) -> None:
        """Submit login form."""
        data = {
            "authenticity_token": self._csrf,
            "user[login]": self._username,
            "user[password]": self._password,
            "gdpr": "1",
            "user[remember_me]": "1",
        }
        try:
            async with async_timeout.timeout(10):
                resp = await self._session.post(
                    LOGIN_URL,
                    data=data,
                    headers={"content-type": "application/x-www-form-urlencoded"},
                    cookies=self._cookies(),
                    allow_redirects=False,
                )
        except TimeoutError as exc:
            raise One2TrackApiClientCommunicationError(
                "Timeout during login"
            ) from exc
        except (aiohttp.ClientError, socket.gaierror) as exc:
            raise One2TrackApiClientCommunicationError(
                f"Error during login: {exc}"
            ) from exc

        if resp.status == 302 and "Set-Cookie" in resp.headers:
            self._cookie = self._parse_cookie(resp)
            if not self._cookie:
                raise One2TrackApiClientAuthenticationError(
                    f"Login succeeded but session cookie '{SESSION_COOKIE}' not found in response"
                )
        else:
            raise One2TrackApiClientAuthenticationError(
                "Invalid username or password"
            )

    async def _async_discover_account_id(self) -> None:
        """Follow redirect from base URL to discover account ID."""
        try:
            async with async_timeout.timeout(10):
                resp = await self._session.get(
                    BASE_URL + "/",
                    cookies=self._cookies(),
                    allow_redirects=False,
                )
        except TimeoutError as exc:
            raise One2TrackApiClientCommunicationError(
                "Timeout discovering account"
            ) from exc
        except (aiohttp.ClientError, socket.gaierror) as exc:
            raise One2TrackApiClientCommunicationError(
                f"Error discovering account: {exc}"
            ) from exc

        if resp.status == 302 and "Location" in resp.headers:
            location = resp.headers["Location"]
            # Extract path from Location header (handles both absolute and
            # relative URLs).  Absolute example:
            #   https://www.one2trackgps.com/users/12345/devices
            # Relative example:
            #   /users/12345/devices
            parsed = urlparse(location)
            path_parts = [p for p in parsed.path.split("/") if p]
            # Expect path like /users/<account_id>/...
            if len(path_parts) >= 2:
                self._account_id = path_parts[1]
                return
        raise One2TrackApiClientAuthenticationError(
            "Could not discover account ID after login"
        )

    async def _async_ensure_authenticated(self) -> None:
        """Re-authenticate if session is missing."""
        if not self._cookie:
            await self.async_authenticate()

    async def _async_refresh_csrf(self) -> str:
        """Get a fresh CSRF token from login page."""
        try:
            async with async_timeout.timeout(10):
                resp = await self._session.get(LOGIN_URL, cookies=self._cookies())
        except TimeoutError as exc:
            raise One2TrackApiClientCommunicationError(
                "Timeout refreshing CSRF"
            ) from exc
        except (aiohttp.ClientError, socket.gaierror) as exc:
            raise One2TrackApiClientCommunicationError(
                f"Error refreshing CSRF: {exc}"
            ) from exc

        if resp.status != 200:
            raise One2TrackApiClientAuthenticationError(
                "Could not refresh CSRF token"
            )
        html = await resp.text()
        new_cookie = self._parse_cookie(resp)
        if new_cookie:
            self._cookie = new_cookie
        self._csrf = self._parse_csrf(html)
        return self._csrf

    # ── Device Discovery ────────────────────────────────────────────

    async def async_discover_devices(self) -> list[dict[str, Any]]:
        """Discover devices via JSON endpoint.

        Returns list of device dicts with uuid, name, serial_number, etc.
        """
        await self._async_ensure_authenticated()
        url = f"{BASE_URL}/users/{self._account_id}/devices"

        try:
            async with async_timeout.timeout(15):
                resp = await self._session.get(
                    url,
                    headers={
                        "Accept": "application/json",
                        "content-type": "application/json",
                    },
                    cookies=self._cookies(),
                )
        except TimeoutError as exc:
            raise One2TrackApiClientCommunicationError(
                "Timeout fetching device list"
            ) from exc
        except (aiohttp.ClientError, socket.gaierror) as exc:
            raise One2TrackApiClientCommunicationError(
                f"Error fetching device list: {exc}"
            ) from exc

        if resp.status in (401, 302):
            self._cookie = ""
            raise One2TrackApiClientAuthenticationError(
                f"Device list returned {resp.status}"
            )
        if resp.status != 200:
            raise One2TrackApiClientCommunicationError(
                f"Device list returned {resp.status}"
            )

        # The server may return HTML (login page) instead of JSON when
        # the session is invalid, even with a 200 status code.
        body = await resp.text()
        if not body or body.lstrip().startswith(("<", "<!DOCTYPE")):
            self._cookie = ""
            raise One2TrackApiClientAuthenticationError(
                "Device list returned HTML instead of JSON — session likely expired"
            )

        try:
            data = json.loads(body)
        except (json.JSONDecodeError, ValueError) as exc:
            raise One2TrackApiClientCommunicationError(
                f"Device list returned invalid JSON: {body[:200]}"
            ) from exc

        try:
            devices = [item["device"] for item in data]
            self._device_uuids = [d["uuid"] for d in devices]
        except (KeyError, TypeError) as exc:
            raise One2TrackApiClientCommunicationError(
                f"Unexpected device list structure: {exc}"
            ) from exc
        return devices

    # ── Device State (HTML scraping) ────────────────────────────────

    async def async_get_device_state(self, uuid: str) -> dict[str, Any]:
        """Fetch rich device state by scraping the per-device HTML page.

        Returns a dict with 'device' and 'last_location' keys.
        """
        await self._async_ensure_authenticated()
        url = f"{BASE_URL}/devices/{uuid}"

        try:
            async with async_timeout.timeout(15):
                resp = await self._session.get(url, cookies=self._cookies())
        except TimeoutError as exc:
            raise One2TrackApiClientCommunicationError(
                f"Timeout fetching device {uuid}"
            ) from exc
        except (aiohttp.ClientError, socket.gaierror) as exc:
            raise One2TrackApiClientCommunicationError(
                f"Error fetching device {uuid}: {exc}"
            ) from exc

        if resp.status in (401, 302):
            self._cookie = ""
            raise One2TrackApiClientAuthenticationError("Session expired")
        if resp.status != 200:
            raise One2TrackApiClientCommunicationError(
                f"Device page for {uuid} returned {resp.status}"
            )

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
                pass

        location_match = re.search(
            r"var last_location\s*=\s*(\{.*?\})\s*;", html, re.DOTALL
        )
        if location_match:
            try:
                result["last_location"] = json.loads(location_match.group(1))
            except json.JSONDecodeError:
                pass

        return result

    async def async_get_all_device_states(self) -> dict[str, dict[str, Any]]:
        """Fetch state for all known devices. Returns {uuid: state_dict}."""
        await self._async_ensure_authenticated()

        if not self._device_uuids:
            await self.async_discover_devices()

        states: dict[str, dict[str, Any]] = {}
        for uuid in self._device_uuids:
            try:
                state = await self.async_get_device_state(uuid)
                if state:
                    states[uuid] = state
            except One2TrackApiClientAuthenticationError:
                await self.async_authenticate()
                state = await self.async_get_device_state(uuid)
                if state:
                    states[uuid] = state

        return states

    # ── Commands (settings & actions) ───────────────────────────────

    async def async_send_command(
        self,
        uuid: str,
        cmd_code: str,
        cmd_values: list[str] | None = None,
    ) -> bool:
        """Send a command to a device.

        Uses POST /api/devices/{uuid}/functions with form-encoded data.
        """
        await self._async_ensure_authenticated()
        csrf = await self._async_refresh_csrf()

        url = f"{BASE_URL}/api/devices/{uuid}/functions"

        form_data: dict[str, str] = {
            "utf8": "\u2713",
            "function[code]": cmd_code,
        }
        if cmd_values:
            form_data["function[value]"] = ",".join(cmd_values)

        try:
            async with async_timeout.timeout(15):
                resp = await self._session.post(
                    url,
                    data=form_data,
                    headers={
                        "x-csrf-token": csrf,
                        "x-requested-with": "XMLHttpRequest",
                        "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
                    },
                    cookies=self._cookies(),
                )
        except TimeoutError as exc:
            raise One2TrackApiClientCommunicationError(
                f"Timeout sending command {cmd_code} to {uuid}"
            ) from exc
        except (aiohttp.ClientError, socket.gaierror) as exc:
            raise One2TrackApiClientCommunicationError(
                f"Error sending command {cmd_code} to {uuid}: {exc}"
            ) from exc

        return resp.status == 200

    # ── Messages ────────────────────────────────────────────────────

    async def async_send_message(self, uuid: str, message: str) -> bool:
        """Send a text message to a device."""
        await self._async_ensure_authenticated()
        csrf = await self._async_refresh_csrf()

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

        try:
            async with async_timeout.timeout(15):
                resp = await self._session.post(
                    url, data=data, headers=headers, cookies=self._cookies()
                )
        except TimeoutError as exc:
            raise One2TrackApiClientCommunicationError(
                f"Timeout sending message to {uuid}"
            ) from exc
        except (aiohttp.ClientError, socket.gaierror) as exc:
            raise One2TrackApiClientCommunicationError(
                f"Error sending message to {uuid}: {exc}"
            ) from exc

        return resp.status == 200

    # ── Raw data (for diagnostics / testing) ───────────────────────

    async def async_get_raw_device_data(self, uuid: str) -> dict[str, Any]:
        """Fetch raw live data for a device from all sources.

        Returns a dict with:
        - json_api: raw device data from the JSON discovery endpoint
        - html_scraped: device + last_location from the HTML page
        - account_id: the resolved account ID
        """
        await self._async_ensure_authenticated()

        result: dict[str, Any] = {"account_id": self._account_id}

        # 1. Fresh JSON from the device list endpoint
        try:
            url = f"{BASE_URL}/users/{self._account_id}/devices"
            async with async_timeout.timeout(15):
                resp = await self._session.get(
                    url,
                    headers={"Accept": "application/json", "content-type": "application/json"},
                    cookies=self._cookies(),
                )
            if resp.status == 200:
                body = await resp.text()
                if body and not body.lstrip().startswith(("<", "<!DOCTYPE")):
                    data = json.loads(body)
                    for item in data:
                        dev = item.get("device", {})
                        if dev.get("uuid") == uuid:
                            result["json_api"] = item
                            break
        except Exception as exc:  # noqa: BLE001
            result["json_api_error"] = str(exc)

        # 2. HTML-scraped data from the device page
        try:
            state = await self.async_get_device_state(uuid)
            result["html_scraped"] = state
        except Exception as exc:  # noqa: BLE001
            result["html_scraped_error"] = str(exc)

        return result

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
        match = re.search(r'name="authenticity_token"[^>]+value="([^"]+)"', html)
        if match:
            return match.group(1)
        raise One2TrackApiClientAuthenticationError("CSRF token not found")

    @staticmethod
    def _parse_cookie(response: aiohttp.ClientResponse) -> str:
        # Check ALL Set-Cookie headers — aiohttp sends multiple and
        # headers.get() only returns the first one.
        for set_cookie in response.headers.getall("Set-Cookie", []):
            if SESSION_COOKIE in set_cookie:
                part = set_cookie.split(SESSION_COOKIE + "=")[1]
                return part.split(";")[0]
        return ""
