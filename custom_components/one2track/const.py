"""Constants for the One2Track integration."""

import logging

DOMAIN = "one2track"
LOGGER = logging.getLogger(__package__)

DEFAULT_UPDATE_INTERVAL_SECONDS = 60

BASE_URL = "https://www.one2trackgps.com"
LOGIN_URL = f"{BASE_URL}/auth/users/sign_in"
SESSION_COOKIE = "_iadmin"

# Config keys
CONF_USER_NAME = "Username"
CONF_PASSWORD = "Password"
CONF_ID = "AccountID"

# Command codes
CMD_SOS_NUMBER = "0001"
CMD_FACTORY_RESET = "0011"
CMD_REFRESH_LOCATION = "0039"
CMD_REMOTE_SHUTDOWN = "0048"
CMD_ALARMS = "0057"
CMD_CHANGE_PASSWORD = "0067"
CMD_GPS_INTERVAL = "0078"
CMD_STEP_COUNTER = "0079"
CMD_WHITELIST_1 = "0080"
CMD_WHITELIST_2 = "0081"
CMD_INTERCOM = "0084"
CMD_LANGUAGE_TIMEZONE = "0124"
CMD_FIND_DEVICE = "1015"
CMD_QUIET_TIMES = "1107"
CMD_PROFILE_MODE = "1116"
CMD_PHONEBOOK = "1315"

# GPS interval options (value -> label)
GPS_INTERVAL_OPTIONS = {
    "10": "10 seconds (high battery usage)",
    "300": "5 minutes (medium battery usage)",
    "600": "10 minutes (low battery usage)",
}

# Profile mode options (value -> label)
PROFILE_MODE_OPTIONS = {
    "1": "Vibrate & Sound",
    "2": "Sound only",
    "3": "Vibrate only",
    "4": "Silent",
}
