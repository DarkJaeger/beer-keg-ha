from __future__ import annotations

# Domain
DOMAIN = "beer_keg"

# Config keys
CONF_WS_URL = "ws_url"
CONF_EMPTY_WEIGHT = "empty_weight"
CONF_DEFAULT_FULL_WEIGHT = "default_full_weight"
CONF_POUR_THRESHOLD = "pour_threshold"
CONF_PER_KEG_FULL = "per_keg_full"  # JSON mapping keg_id -> full weight

# Defaults
DEFAULT_EMPTY_WEIGHT = 4.0
DEFAULT_FULL_WEIGHT = 19.0
DEFAULT_POUR_THRESHOLD = 0.15  # kg
DEFAULT_PER_KEG_FULL_JSON = "{}"

# Storage
HISTORY_FILE = ".storage/beer_keg_history.json"
MAX_LOG_ENTRIES = 500

# Sensor meta used by sensor.py
SENSOR_TYPES = {
    "temperature": {
        "unit": "°C",
        "name": "Temperature",
        "icon": "mdi:thermometer",
        "device_class": "temperature",
        "state_class": "measurement",
        "key": "temperature",
    },
    "full_weight": {
        "unit": "kg",
        "name": "Full Weight",
        "icon": "mdi:scale-bathroom",
        "device_class": None,
        "state_class": "measurement",
        "key": "full_weight",
    },
    "weight": {
        "unit": "kg",
        "name": "Weight",
        "icon": "mdi:scale",
        "device_class": None,
        "state_class": "measurement",
        "key": "weight",
    },
    "daily_consumed": {
        "unit": "kg",
        "name": "Daily Consumed",
        "icon": "mdi:calendar-today",
        "device_class": None,
        "state_class": "measurement",
        "key": "daily_consumed",
    },
    "last_pour": {
        "unit": "kg",
        "name": "Last Pour",
        "icon": "mdi:cup",
        "device_class": None,
        "state_class": "measurement",
        "key": "last_pour",
    },
    "fill_percent": {
        "unit": "%",
        "name": "Fill Level",
        "icon": "mdi:beer",
        "device_class": None,
        "state_class": "measurement",
        "key": "fill_percent",
    },
    "name": {
        "unit": None,
        "name": "Name",
        "icon": "mdi:barcode",
        "device_class": None,
        "state_class": None,
        "key": "name",
    },
    "id": {
        "unit": None,
        "name": "ID",
        "icon": "mdi:identifier",
        "device_class": None,
        "state_class": None,
        "key": "id",
    },
}
