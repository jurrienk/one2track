# CLAUDE.md — One2Track Integration

## What This Is

A custom Home Assistant integration for One2Track GPS watches (children/elderly trackers). Domain: `one2track`. There is no official API — the integration scrapes `www.one2trackgps.com` using session cookies, CSRF tokens, and HTML parsing.

## Key Files

- `custom_components/one2track/api.py` — All HTTP communication (auth, scraping, commands)
- `custom_components/one2track/coordinator.py` — DataUpdateCoordinator, merges JSON + HTML data
- `custom_components/one2track/services.py` — All HA service handlers and registration
- `custom_components/one2track/entity.py` — Base entity class (shared device_info, data access)
- `custom_components/one2track/const.py` — Command codes, URLs, constants
- `custom_components/one2track/sensor.py` — 12 sensor entities
- `custom_components/one2track/device_tracker.py` — GPS tracker entity with attributes
- `custom_components/one2track/switch.py` — Step counter toggle
- `custom_components/one2track/select.py` — GPS interval + profile mode selectors
- `custom_components/one2track/button.py` — Refresh location + find device buttons
- `custom_components/one2track/binary_sensor.py` — Fall detection
- `TESTING.md` — Full architecture, entity reference, service examples, test procedures

## Critical Implementation Details

These have caused regressions before — do not change without understanding:

1. **Command endpoint URL must include `/api/`**: `POST /api/devices/{uuid}/functions` (not `/devices/{uuid}/functions`)
2. **Command field names**: `function[code]` and `function[value]` (not `function[cmd_code]` or `function[cmd_value][]`)
3. **Command headers must include**: `x-csrf-token` and `x-requested-with: XMLHttpRequest`
4. **Session must be dedicated**: Use `async_create_clientsession(hass)` not `async_get_clientsession(hass)` — shared session causes auth failures
5. **Account ID extraction**: The login redirect URL is absolute (`https://www.one2trackgps.com/users/12345/devices`), parse with `urlparse` — don't naively split on `/`
6. **`balance_cents` API field contains euros**, not cents. Don't divide by 100.
7. **Services must accept `device_id`, `entity_id`, and `area_id`** — HA's automation editor defaults to device_id targeting

## Version Bumping

Always bump the version in `manifest.json` when making changes. Current: `4.0.4`.

## Testing

Read `TESTING.md` for the complete reference. Key diagnostic tool: the `one2track.get_raw_device_data` service returns raw data from all sources (JSON API, HTML scraping, coordinator state) for comparison.

## No Tests / No CI

This repo has no automated tests or CI pipeline. Changes are validated via manual testing on a live HA instance with real One2Track devices.

## Forked From

Originally forked from `vandernorth/one2track` (v2.0.x). Significantly rewritten in v4.0.0 with separate entity platforms, service actions, and HTML scraping. The v2.0.2 codebase is the reference for working API patterns — always compare against it if something breaks (commit `63f7b05`).
