# One2Track Integration Rewrite Plan

## Why rewrite?

The current integration is built on vandernorth's codebase which has several issues:
1. **Wrong API surface** — Uses a JSON device list endpoint (`/users/{id}/devices`) that doesn't expose all fields the per-device HTML page has (e.g. `step_count_day`, `alarm_mode`, `protocol`, `course`)
2. **Wrong command format** — Sends `function[value]` (single string) instead of `function[cmd_value][]` (array), and uses POST instead of PATCH with `_method=patch`
3. **Different backend** — Docs reference `app.one2track.com` with cookie `_session_id` vs current `www.one2trackgps.com` with `_iadmin`. Need to support the documented API properly
4. **Missing functionality** — Only 3 services (send_message, force_update, send_device_command). The API supports 16+ commands, many of which map well to HA entity types (buttons, switches, selects)

## Architecture

```
custom_components/one2track/
├── __init__.py              # Entry setup, service registration
├── manifest.json            # Bump to 3.0.0
├── config_flow.py           # Login flow (username + password)
├── const.py                 # Constants (replaces common.py)
├── coordinator.py           # DataUpdateCoordinator — polls per-device HTML pages
├── api.py                   # API client (replaces client/ package)
├── services.py              # Service handlers
├── services.yaml            # Service definitions
├── device_tracker.py        # GPS tracker entity
├── sensor.py                # Sensor entities
├── binary_sensor.py         # Fall detection
├── button.py                # NEW: Refresh location, Find device
├── switch.py                # NEW: Step counter toggle
├── select.py                # NEW: GPS interval, Profile mode
├── strings.json             # Translations
└── translations/
    └── en.json
```

### Flatten client/ into single api.py
No need for a sub-package. One file with the `One2TrackAPI` class.

---

## Step 1: API Client (`api.py`)

New `One2TrackAPI` class, from scratch.

### Authentication
- `POST /auth/users/sign_in` with CSRF token from login page
- Store `_session_id` cookie (fall back to `_iadmin` if needed — test which works)
- Re-authenticate on 401 or login redirect

### Device discovery
- `GET /users/{username}/devices` — parse HTML sidebar for device UUIDs and names
- Store list of `(uuid, name, serial_number)` tuples

### Device state (per-device polling)
- `GET /devices/{uuid}` — parse `var device = {...};` and `var last_location = {...};` from HTML
- Returns rich data: battery, location, steps_today, alarm_mode, protocol, status, etc.
- This replaces the current JSON list endpoint and gives us MORE data

### Command sending
- `PATCH /devices/{uuid}/functions` (actually POST with `_method=patch` in form body)
- CSRF token required
- `function[cmd_code]` + zero or more `function[cmd_value][]` entries
- Use list of tuples for form data to support repeated keys:
  ```python
  data = [
      ("utf8", "✓"),
      ("_method", "patch"),
      ("authenticity_token", csrf),
      ("function[cmd_code]", cmd_code),
      ("function[cmd_value][]", value1),
      ("function[cmd_value][]", value2),
  ]
  ```

### Message sending
- Keep existing message endpoint (test against both hostnames)

---

## Step 2: Coordinator (`coordinator.py`)

- Polls each device individually via `GET /devices/{uuid}`
- Update interval: 60 seconds (configurable later)
- First discovers device list, then polls each
- Stores parsed device + location dicts per UUID

---

## Step 3: Entities

### Device Tracker (`device_tracker.py`)
Same as current but consuming the new parsed data format. Fields:
- latitude, longitude, battery_level, location_accuracy, location_name (zone detection)
- Extra attributes: address, location_type, status, phone_number, serial_number

### Sensors (`sensor.py`)
Keep existing sensors, add new ones from the richer data:
- battery, signal_strength, satellite_count, speed, altitude, accuracy, status
- last_communication, last_location_update (timestamps)
- **steps_today** (new: `step_count_day` from device page — daily counter, not lifetime)
- **heading** (new: `meta_data.course` — compass bearing)

Drop: sim_balance (not available in per-device HTML, check if still accessible)

### Binary Sensor (`binary_sensor.py`)
- Fall detection (tumble) — same as current

### Buttons (`button.py`) — NEW
- **Refresh Location** — sends cmd `0039`, activates GPS for 2 min
- **Find Device (Ring)** — sends cmd `1015`, plays ringtone on watch

### Switch (`switch.py`) — NEW
- **Step Counter** — sends cmd `0079` with value `1` (on) or no value (off)
- State tracked locally after toggle (API doesn't report this back cleanly)

### Select (`select.py`) — NEW
- **GPS Tracking Interval** — cmd `0078`, options: "10 seconds" / "5 minutes" / "10 minutes"
- **Profile Mode** — cmd `1116`, options: "Vibrate & Sound" / "Sound only" / "Vibrate only" / "Silent"
- State tracked locally after selection

---

## Step 4: Services (`services.py` + `services.yaml`)

### Keep: `send_device_command` (generic)
Updated to use the correct `function[cmd_value][]` array format.
Fields: `entity_id`, `cmd_code`, `cmd_values` (list of strings, replaces old cmd_value + cmd_value_param)

### Keep: `force_update`
Convenience wrapper for cmd `0039`. Also triggers coordinator refresh.

### Keep: `send_message`
Text message to device.

### New services:
| Service | Command | Fields |
|---------|---------|--------|
| `set_sos_number` | 0001 | `phone_number` |
| `intercom` | 0084 | `phone_number` (watch calls this number) |
| `set_alarms` | 0057 | `alarms` (list of alarm strings) |
| `set_phonebook` | 1315 | `contacts` (list of {name, number} pairs) |
| `set_whitelist` | 0080+0081 | `phone_numbers` (list of up to 10 numbers) |
| `set_quiet_times` | 1107 | `windows` (list of {start, end} times) |
| `set_language_timezone` | 0124 | `language`, `utc_offset` |
| `change_password` | 0067 | `password` (6-digit PIN) |
| `factory_reset` | 0011 | (no fields — dangerous, log warning) |
| `remote_shutdown` | 0048 | (no fields — dangerous, log warning) |

---

## Step 5: Config Flow (`config_flow.py`)

Simplified:
1. Ask for username + password
2. Login to discover account
3. Discover devices to validate credentials work
4. Store username + password (no account_id needed if we discover per-device)

Use standard HA config keys (`CONF_USERNAME`, `CONF_PASSWORD`) instead of custom strings.

---

## Step 6: Translations & Strings

Update `strings.json` and `translations/en.json` for all new entities and services.

---

## Implementation Order

1. `const.py` — constants
2. `api.py` — new API client (auth, device discovery, state parsing, command sending)
3. `coordinator.py` — new coordinator using api.py
4. `config_flow.py` — simplified config flow
5. `__init__.py` — entry setup with new structure
6. `device_tracker.py` — rewrite for new data format
7. `sensor.py` — rewrite with new + updated sensors
8. `binary_sensor.py` — minor update for new data format
9. `button.py` — new: refresh location + find device
10. `switch.py` — new: step counter
11. `select.py` — new: GPS interval + profile mode
12. `services.py` + `services.yaml` — all services
13. `strings.json` + `translations/en.json` — translations
14. `manifest.json` — bump version to 3.0.0
15. Clean up: remove `client/` sub-package, `common.py`

---

## Open Questions

1. **Base URL**: Docs say `app.one2track.com`, current code uses `www.one2trackgps.com`. Do both work? Should we try `app.one2track.com` first?
2. **SIM balance**: The per-device HTML page may not include simcard balance data. Should we keep the JSON list endpoint as a fallback, or drop this sensor?
3. **Version migration**: Do we need a config flow migration from v1 → v2 for existing users, or is a clean re-add acceptable?
