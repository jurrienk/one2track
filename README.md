# One2Track — Home Assistant Integration

Custom Home Assistant integration for [One2Track](https://www.one2trackgps.com) GPS watches (children's and elderly trackers).

## Features

- **Device tracker** with GPS coordinates, zone detection, and address
- **12 sensors** — battery, SIM balance, signal strength, satellite count, speed, altitude, heading, GPS accuracy, steps, status, and timestamps
- **Binary sensor** — fall detection
- **Buttons** — refresh location (activate GPS mode), find device (ring the watch)
- **Switch** — step counter toggle
- **Selects** — GPS tracking interval, profile/sound mode
- **15 services** — send message, force update, find device, intercom, set SOS number, set alarms, set phonebook, set whitelist, set quiet times, set language/timezone, change password, factory reset, remote shutdown, and a raw diagnostics service
- **Multi-model support** — automatically discovers each watch's capabilities (Connect MOVE, Connect UP, and others)
- **Device targeting** — all services support `entity_id`, `device_id`, and `area_id` targeting

## Installation

### HACS (recommended)

1. Open HACS in your Home Assistant instance
2. Go to **Integrations** and click the three-dot menu in the top right
3. Select **Custom repositories**
4. Add `https://github.com/jurrienk/one2track` with category **Integration**
5. Search for "One2Track" and install it
6. Restart Home Assistant
7. Go to **Settings > Devices & Services > Add Integration** and search for **One2Track**
8. Enter your One2Track portal username and password

### Manual

1. Copy the `custom_components/one2track` folder to your Home Assistant `config/custom_components/` directory
2. Restart Home Assistant
3. Add the integration via **Settings > Devices & Services**

## Supported Devices

The integration auto-discovers your watches and their capabilities. Tested with:

- **Connect UP** (model_id 77) — GPS interval code 0077, step counter code 0082
- **Connect MOVE** (model_id 27) — GPS interval code 0078, step counter code 0079, plus whitelist, intercom, and password change

Other One2Track watch models should work — the integration discovers available commands dynamically rather than hardcoding per model.

## How It Works

There is no official One2Track API. This integration communicates with `www.one2trackgps.com` (a Ruby on Rails web application) by:

1. Authenticating via the login form with session cookies and CSRF tokens
2. Polling device state by scraping inline JavaScript variables from device pages
3. Refreshing base data from the JSON device list endpoint
4. Sending commands via form POSTs that mimic the web portal's PATCH requests

## Diagnostics

Call the `one2track.get_raw_device_data` service to get raw data from all sources (JSON API, HTML scraping, coordinator state, discovered capabilities). This is invaluable for debugging data issues.

## Documentation

See [TESTING.md](TESTING.md) for the full architecture reference, entity specifications, service examples, and test procedures.
