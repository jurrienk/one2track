# One2Track Integration — Testing & Architecture Reference

> **Version:** 4.0.4
> **Integration domain:** `one2track`
> **Source:** `custom_components/one2track/`

This document is the single reference for testing the One2Track custom integration for Home Assistant. It covers architecture, data flow, all entities, all services, known limitations, and test procedures.

---

## 1. Architecture Overview

The integration communicates with `www.one2trackgps.com` — there is no official API. It uses session-based web authentication (cookies + CSRF tokens) and two data sources:

### Data Sources

| Source | URL pattern | Returns | Used for |
|--------|------------|---------|----------|
| **JSON API** | `GET /users/{account_id}/devices` | Array of `{device: {...}}` objects | Initial device discovery (uuid, name, serial, simcard, phone_number, status) |
| **HTML scraping** | `GET /devices/{uuid}` | HTML page with embedded `var device = {...}` and `var last_location = {...}` JS vars | Periodic state updates (battery, location, signal, speed, etc.) |

### Data Flow

```
Login → GET /auth/users/sign_in (get CSRF + cookie)
      → POST /auth/users/sign_in (authenticate)
      → GET / (redirect reveals account_id)

Discovery → GET /users/{account_id}/devices (JSON, Accept: application/json)
          → Returns list of devices with uuid, name, serial_number, simcard, status

Polling (every 60s) → For each device UUID:
                     → GET /devices/{uuid} (HTML page)
                     → Parse "var device = {...}" and "var last_location = {...}"
                     → Merge with discovery data

Commands → POST /api/devices/{uuid}/functions
         → Headers: x-csrf-token, x-requested-with: XMLHttpRequest
         → Body: function[code]=XXXX, function[value]=...
```

### Coordinator Merging

The coordinator (`coordinator.py`) merges data from both sources via `get_device_data(uuid)`:
1. Starts with the JSON discovery data as the base
2. Overlays the HTML-scraped `device` dict (takes precedence for overlapping keys)
3. Attaches `last_location` from HTML scraping

All entities read from this merged dict via `self._data` (device-level) and `self._location` (last_location sub-dict).

---

## 2. Entity Reference

Each physical device (watch) creates the following HA entities:

### Device Tracker

| Entity ID pattern | `device_tracker.<name>` |
|---|---|
| **unique_id** | `{uuid}` |
| **Source** | Merged data |
| **Provides** | latitude, longitude, location_accuracy, battery_level, location_name (zone or address) |

**Extra state attributes:**
- `serial_number`, `uuid`, `status`, `phone_number`
- `location_type` (GPS/WIFI/LBS), `address`, `altitude`
- `signal_strength`, `satellite_count`
- `last_communication`, `last_location_update`
- `tariff_type`, `balance_eur` (from simcard data — note: the API field is called `balance_cents` but contains euro values)

### Sensors

| Key | Entity suffix | Source field | Unit | Notes |
|-----|--------------|-------------|------|-------|
| `battery` | `_battery` | `last_location.battery_percentage` | % | Standard battery device class |
| `sim_balance` | `_sim_balance` | `simcard.balance_cents` | EUR | **Value is euros despite API field name**. Displayed as `round(float(value), 2)` |
| `last_location_update` | `_last_location_update` | `last_location.last_location_update` | timestamp | ISO format |
| `last_communication` | `_last_communication` | `last_location.last_communication` | timestamp | ISO format |
| `signal_strength` | `_signal_strength` | `last_location.signal_strength` | % | |
| `satellite_count` | `_satellite_count` | `last_location.satellite_count` | count | 0 = no GPS fix (WIFI/LBS positioning) |
| `speed` | `_speed` | `last_location.speed` | km/h | |
| `altitude` | `_altitude` | `last_location.altitude` | m | |
| `steps_today` | `_steps_today` | `last_location.step_count_day` | steps | Resets daily |
| `accuracy` | `_accuracy` | `last_location.meta_data.accuracy_meters` | m | GPS accuracy radius |
| `heading` | `_heading` | `last_location.meta_data.course` | ° | Returns `unknown` when satellite_count is 0 (no GPS fix) |
| `status` | `_status` | `device.status` | string | Plain text (e.g. "online", "offline"). Comes from JSON discovery data |

### Binary Sensors

| Key | Entity suffix | Source field | Device class | Notes |
|-----|--------------|-------------|-------------|-------|
| `tumble` | `_fall_detected` | `last_location.meta_data.tumble` | safety | `"1"` = fall detected |

### Buttons

| Key | Entity suffix | Command code | Notes |
|-----|--------------|-------------|-------|
| `refresh_location` | `_refresh_location` | `0039` | Activates high-frequency GPS for ~2 min |
| `find_device` | `_find_device` | `1015` | Makes the watch ring |

### Switches

| Key | Entity suffix | Command code | Notes |
|-----|--------------|-------------|-------|
| `step_counter` | `_step_counter` | `0079` | `["1"]` to enable, no value to disable. **Assumed state** — cannot read current setting from API. Defaults to ON. |

### Selects

| Key | Entity suffix | Command code | Options (api_value → label) |
|-----|--------------|-------------|---------------------------|
| `gps_interval` | `_gps_tracking_interval` | `0078` | `10` → "10 seconds (high battery usage)", `300` → "5 minutes", `600` → "10 minutes" |
| `profile_mode` | `_profile_mode` | `1116` | `1` → "Vibrate & Sound", `2` → "Sound only", `3` → "Vibrate only", `4` → "Silent" |

---

## 3. Services Reference

All services accept targeting via `entity_id`, `device_id`, or `area_id`. The service resolves any of these to the device UUID internally.

### Action Services

#### `one2track.send_message`
Send a text message to the watch display.
```yaml
service: one2track.send_message
target:
  device_id: <device_id>
data:
  message: "Time to come home!"
```

#### `one2track.force_update`
Activate high-frequency GPS mode (~2 minutes). Also triggers a coordinator refresh.
```yaml
service: one2track.force_update
target:
  device_id: <device_id>
```

#### `one2track.find_device`
Make the watch play its ringtone.
```yaml
service: one2track.find_device
target:
  device_id: <device_id>
```

#### `one2track.intercom`
Make the watch immediately call the specified phone number.
```yaml
service: one2track.intercom
target:
  device_id: <device_id>
data:
  phone_number: "0031612345678"
```

### Setting Services

#### `one2track.send_device_command`
Send an arbitrary command code to the device. Generic escape hatch.
```yaml
service: one2track.send_device_command
target:
  device_id: <device_id>
data:
  cmd_code: "0039"
  cmd_values:              # optional, list of strings
    - "value1"
```

#### `one2track.set_sos_number`
```yaml
data:
  phone_number: "0031612345678"
```

#### `one2track.set_alarms`
Format per alarm: `HH:MM-STATUS-MODE[-DDDDDDD]`. Send empty list to clear.
```yaml
data:
  alarms:
    - "07:00-1-2"              # daily at 07:00
    - "08:30-1-3-1111100"      # weekdays at 08:30
```

#### `one2track.set_phonebook`
```yaml
data:
  contacts:
    - name: "Papa"
      number: "0031612345678"
    - name: "Mama"
      number: "0031687654321"
```

#### `one2track.set_whitelist`
Up to 10 phone numbers allowed to call the watch.
```yaml
data:
  phone_numbers:
    - "0031612345678"
    - "0031687654321"
```

#### `one2track.set_quiet_times`
Up to 3 silent windows. Send empty list to clear.
```yaml
data:
  windows:
    - start: "22:00"
      end: "07:00"
```

#### `one2track.set_language_timezone`
```yaml
data:
  language: "16"        # 1=English, 5=German, 16=Dutch
  utc_offset: "1.0"     # CET=1.0, CEST=2.0
```

#### `one2track.change_password`
Change the 6-digit PIN on the watch.
```yaml
data:
  password: "123456"     # must be exactly 6 digits
```

#### `one2track.factory_reset`
**DANGEROUS.** Resets the device to factory defaults. Cannot be undone.

#### `one2track.remote_shutdown`
**DANGEROUS.** Powers off the watch remotely. Cannot be turned back on via the app.

### Diagnostics Service

#### `one2track.get_raw_device_data`
Fetches live raw data from all sources and returns it as response data. Use this to compare what the One2Track website actually returns vs what HA displays.

```yaml
service: one2track.get_raw_device_data
target:
  device_id: <device_id>
data: {}
```

**Response structure:**
```json
{
  "account_id": "12345",
  "json_api": {
    "device": {
      "uuid": "...",
      "name": "...",
      "serial_number": "...",
      "status": "online",
      "phone_number": "...",
      "simcard": {
        "balance_cents": 399.599,
        "tariff_type": "prepaid"
      }
    }
  },
  "html_scraped": {
    "device": { "...fields from var device JS var..." },
    "last_location": {
      "latitude": 52.xxx,
      "longitude": 4.xxx,
      "battery_percentage": 85,
      "signal_strength": 90,
      "satellite_count": 7,
      "speed": 0,
      "altitude": 5.0,
      "location_type": "GPS",
      "address": "...",
      "meta_data": {
        "accuracy_meters": 15,
        "course": 180.0,
        "tumble": "0"
      }
    }
  },
  "coordinator_data": {
    "...merged dict that HA entities actually read from..."
  }
}
```

**How to call from Developer Tools:**
1. Go to Developer Tools → Services
2. Select `one2track.get_raw_device_data`
3. Select target device
4. Toggle "Return response" ON
5. Call the service — raw data appears in the response panel

**How to call from CLI/API:**
```bash
curl -X POST http://homeassistant.local:8123/api/services/one2track/get_raw_device_data?return_response \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"device_id": "DEVICE_ID"}'
```

---

## 4. Command Endpoint Details

All device commands use:
- **URL:** `POST https://www.one2trackgps.com/api/devices/{uuid}/functions`
- **Headers:** `x-csrf-token`, `x-requested-with: XMLHttpRequest`, `content-type: application/x-www-form-urlencoded; charset=UTF-8`
- **Body fields:** `function[code]` (4-digit string), optionally `function[value]` (comma-joined values)

### Command Code Reference

| Code | Name | Values | Notes |
|------|------|--------|-------|
| `0001` | SOS number | phone number | |
| `0011` | Factory reset | none | **Irreversible** |
| `0039` | Refresh location | none | Activates GPS for ~2 min |
| `0048` | Remote shutdown | none | **Cannot restart remotely** |
| `0057` | Alarms | alarm strings | |
| `0067` | Change password | 6-digit PIN | |
| `0078` | GPS interval | `10`, `300`, `600` (seconds) | |
| `0079` | Step counter | `1` to enable, omit to disable | |
| `0080` | Whitelist slots 1-5 | 5 phone numbers | |
| `0081` | Whitelist slots 6-10 | 5 phone numbers | |
| `0084` | Intercom | phone number | Watch calls this number |
| `0124` | Language & timezone | `language,utc_offset` | |
| `1015` | Find device | none | Makes watch ring |
| `1107` | Quiet times | time window strings | |
| `1116` | Profile mode | `1`-`4` | |
| `1315` | Phonebook | `name,number,...` pairs | |

---

## 5. Known Limitations

1. **Step counter switch is assumed state.** There is no API to read the current setting. The switch defaults to ON and tracks state locally. On HA restart it resets to ON.

2. **GPS interval and profile mode selects are assumed state.** Same limitation — no API to read current setting. They show the last-selected option.

3. **Status sensor depends on JSON discovery data.** The `status` field comes from the initial device discovery endpoint, not from the HTML page. It may not update as frequently as other sensors.

4. **HTML scraping is fragile.** The integration parses `var device = {...}` and `var last_location = {...}` from inline JavaScript. If One2Track changes their page structure, scraping will silently return empty dicts.

5. **Session can expire.** The integration re-authenticates automatically when it detects a 302/401, but there may be edge cases where the cookie jar gets stale.

6. **The `balance_cents` API field contains euros, not cents.** The attribute is named `balance_eur` and the `sim_balance` sensor displays the value directly without conversion.

7. **Heading reads `unknown` when satellite_count is 0.** This is intentional — without GPS fix, heading data (defaulting to 0.0/north) is meaningless.

---

## 6. Test Procedures

### Basic Connectivity Test
1. Check the integration loaded: confirm devices appear under Settings → Devices
2. Verify the device tracker entity has latitude/longitude
3. Check `sensor.*_battery` has a percentage value
4. Check `sensor.*_status` shows a string value (not 404)

### Service Targeting Test
Services must work with all three targeting methods:
```yaml
# By entity_id
service: one2track.find_device
target:
  entity_id: device_tracker.my_watch

# By device_id
service: one2track.find_device
target:
  device_id: <ha_device_id>

# By area_id (if device is assigned to an area)
service: one2track.find_device
target:
  area_id: <area_id>
```

### Data Accuracy Test
1. Call `one2track.get_raw_device_data` with return_response
2. Compare `json_api.device` fields with entity attributes
3. Compare `html_scraped.last_location` fields with sensor values
4. Check `coordinator_data` matches what entities display
5. Verify `balance_eur` attribute matches `sim_balance` sensor value

### Command Test (safe commands only)
- **find_device:** Watch should ring audibly. Verify service returns without error.
- **force_update:** Call service, wait 30-60s, check if `last_location_update` timestamp advances.
- **send_message:** Send a test message, verify it appears on the watch screen.
- **send_device_command:** Test with code `0048` (shutdown) only if explicitly authorized.

### Sensor Data Quality Tests
- When `satellite_count` is 0: `heading` should show `unknown`, `location_type` should be WIFI or LBS
- `sim_balance` should show a reasonable EUR value (not 1/100th of expected)
- `battery` should be 0-100
- Timestamps should be recent and in correct timezone

### Entity Registry Test
1. List all entities for the device
2. Every entity should have a state (not 404/unavailable unless the watch is genuinely offline)
3. Check `disabled_by` is null for all expected entities
