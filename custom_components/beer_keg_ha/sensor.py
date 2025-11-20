from __future__ import annotations

import logging
from typing import Any, Dict, List, Set

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORM_EVENT = f"{DOMAIN}_update"

# Base + display sensor definitions.
# "unit" here is the *native* unit our integration stores,
# not necessarily what we want to *display*.
SENSOR_TYPES: Dict[str, Dict[str, Any]] = {
    # --- RAW BASE SENSORS (HA-native, fixed units) ---
    "weight": {
        "unit": "kg",
        "name": "Weight",
        "key": "weight",
        "icon": "mdi:scale",
        "device_class": "weight",
        "state_class": "measurement",
    },
    "temperature": {
        "unit": "°C",
        "name": "Temperature",
        "key": "temperature",
        "icon": "mdi:thermometer",
        "device_class": "temperature",
        "state_class": "measurement",
    },

    # --- DISPLAY SENSORS (follow display_units; no HA auto-conversion) ---
    "weight_display": {
        "unit": None,              # set dynamically
        "name": "Weight (Display)",
        "key": "weight",
        "icon": "mdi:scale",
        "device_class": None,      # avoid HA unit coercion
        "state_class": "measurement",
    },
    "temperature_display": {
        "unit": None,
        "name": "Temperature (Display)",
        "key": "temperature",
        "icon": "mdi:thermometer",
        "device_class": None,
        "state_class": "measurement",
    },

    # --- FILL LEVEL ---
    "fill_percent": {
        "unit": "%",
        "name": "Fill Level",
        "key": "fill_percent",
        "icon": "mdi:cup",
        "device_class": None,
        "state_class": "measurement",
    },
    # legacy alias
    "fill_level": {
        "unit": "%",
        "name": "Fill Level",
        "key": "fill_percent",
        "icon": "mdi:cup",
        "device_class": None,
        "state_class": "measurement",
    },

    # --- POUR / CONSUMPTION (base = oz) ---
    "last_pour": {
        "unit": "oz",
        "name": "Last Pour (oz)",
        "key": "last_pour",
        "icon": "mdi:cup-water",
        "device_class": None,
        "state_class": "measurement",
    },
    "daily_consumed": {
        "unit": "oz",
        "name": "Daily Consumption (oz)",
        "key": "daily_consumed",
        "icon": "mdi:beer",
        "device_class": None,
        "state_class": "total_increasing",
    },

    # --- DISPLAY POUR/CONSUMPTION (oz/ml based on display_units.pour) ---
    "last_pour_display": {
        "unit": None,  # dynamic oz/ml
        "name": "Last Pour (Display)",
        "key": "last_pour",
        "icon": "mdi:cup-water",
        "device_class": None,
        "state_class": "measurement",
    },
    "daily_consumption_display": {
        "unit": None,
        "name": "Daily Consumption (Display)",
        "key": "daily_consumed",
        "icon": "mdi:beer",
        "device_class": None,
        "state_class": "total_increasing",
    },

    # --- FULL WEIGHT / META ---
    "full_weight": {
        "unit": "kg",
        "name": "Full Weight",
        "key": "full_weight",
        "icon": "mdi:weight",
        "device_class": "weight",
        "state_class": "measurement",
    },
    "name": {
        "unit": None,
        "name": "Name",
        "key": "name",
        "icon": "mdi:barcode",
        "device_class": None,
        "state_class": None,
    },
    "id": {
        "unit": None,
        "name": "ID",
        "key": "id",
        "icon": "mdi:identifier",
        "device_class": None,
        "state_class": None,
    },
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up keg sensors for a config entry."""
    state = hass.data[DOMAIN][entry.entry_id]
    created: Set[str] = state.setdefault("created_kegs", set())

    def create_for(keg_id: str) -> None:
        # Create all sensors (raw + display) for one keg_id (once).
        if keg_id in created:
            return

        ents: List[KegSensor] = [
            KegSensor(hass, entry, keg_id, sensor_key)
            for sensor_key in SENSOR_TYPES.keys()
        ]
        async_add_entities(ents, True)
        created.add(keg_id)

    # create for any already-known kegs
    for keg_id in list(state.get("data", {}).keys()):
        create_for(keg_id)

    @callback
    def _on_update(event) -> None:
        """Handle keg update events from the integration."""
        keg_id = (event.data or {}).get("keg_id")
        if keg_id:
            create_for(keg_id)
            # existing sensors for this keg will also be nudged by their own listeners

    entry.async_on_unload(hass.bus.async_listen(PLATFORM_EVENT, _on_update))


class KegSensor(SensorEntity):
    """One logical sensor (weight/temp/etc.) for a specific keg."""

    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        keg_id: str,
        sensor_type: str,
    ) -> None:
        self.hass = hass
        self.entry = entry
        self.keg_id = keg_id
        self.sensor_type = sensor_type

        self._state_ref: Dict[str, Any] = hass.data[DOMAIN][entry.entry_id]
        self._meta = SENSOR_TYPES[sensor_type]

        # Shorten keg id in name for cosmetics
        short_id = keg_id[:4]

        self._attr_name = f"Keg {short_id} {self._meta['name']}"
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_{keg_id}_{sensor_type}"
        self._attr_icon = self._meta.get("icon")
        self._attr_device_class = self._meta.get("device_class")
        self._attr_state_class = self._meta.get("state_class")
        # Start with base unit; display units may adjust this in native_value
        self._attr_native_unit_of_measurement = self._meta.get("unit")

    @property
    def device_info(self) -> DeviceInfo:
        short_id = self.keg_id[:4]
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self.entry.entry_id}_{self.keg_id}")},
            name=f"Beer Keg {short_id}",
            manufacturer="Beer Keg",
            model="WebSocket + REST",
        )

    # ---- helpers ----

    def _get_display_units(self) -> Dict[str, str]:
        """Return normalized display units dict from integration state."""
        du = self._state_ref.get("display_units") or {}
        weight_u = du.get("weight", "kg")
        temp_u = du.get("temp", "°C")
        pour_u = du.get("pour", "oz")

        if weight_u not in ("kg", "lb"):
            weight_u = "kg"
        if temp_u not in ("°C", "°F"):
            temp_u = "°C"
        if pour_u not in ("oz", "ml"):
            pour_u = "oz"

        return {"weight": weight_u, "temp": temp_u, "pour": pour_u}

    # ---- core value ----

    @property
    def native_value(self) -> Any:
        """Return value, converted according to Beer Keg display units."""
        data: Dict[str, Dict[str, Any]] = self._state_ref.get("data", {})
        raw = data.get(self.keg_id, {}).get(self._meta["key"])

        if raw is None:
            return None

        units = self._get_display_units()

        # ========== RAW FIXED-UNIT SENSORS ==========
        if self.sensor_type == "weight":
            # Always base kg for HA
            try:
                raw_kg = float(raw)
            except (TypeError, ValueError):
                return None
            self._attr_native_unit_of_measurement = "kg"
            return round(raw_kg, 2)

        if self.sensor_type == "temperature":
            # Always base °C for HA
            try:
                raw_c = float(raw)
            except (TypeError, ValueError):
                return None
            self._attr_native_unit_of_measurement = "°C"
            return round(raw_c, 1)

        # ========== DISPLAY SENSORS (follow display_units) ==========

        # ---- DISPLAY weight ----
        if self.sensor_type == "weight_display":
            try:
                raw_kg = float(raw)
            except (TypeError, ValueError):
                return None

            if units["weight"] == "lb":
                self._attr_native_unit_of_measurement = "lb"
                return round(raw_kg * 2.20462, 2)
            else:
                self._attr_native_unit_of_measurement = "kg"
                return round(raw_kg, 2)

        # ---- DISPLAY temperature ----
        if self.sensor_type == "temperature_display":
            try:
                raw_c = float(raw)
            except (TypeError, ValueError):
                return None

            if units["temp"] == "°F":
                self._attr_native_unit_of_measurement = "°F"
                return round((raw_c * 9.0 / 5.0) + 32.0, 1)
            else:
                self._attr_native_unit_of_measurement = "°C"
                return round(raw_c, 1)

        # ---- DISPLAY pour: last_pour_display ----
        if self.sensor_type == "last_pour_display":
            try:
                raw_oz = float(raw)
            except (TypeError, ValueError):
                return None

            if units["pour"] == "ml":
                self._attr_native_unit_of_measurement = "ml"
                return round(raw_oz * 29.5735, 0)
            else:
                self._attr_native_unit_of_measurement = "oz"
                return round(raw_oz, 1)

        # ---- DISPLAY pour: daily_consumption_display ----
        if self.sensor_type == "daily_consumption_display":
            try:
                raw_oz = float(raw)
            except (TypeError, ValueError):
                return None

            if units["pour"] == "ml":
                self._attr_native_unit_of_measurement = "ml"
                return round(raw_oz * 29.5735, 0)
            else:
                self._attr_native_unit_of_measurement = "oz"
                return round(raw_oz, 1)

        # ========== BASE POUR / OTHER META (no dynamic conversion here) ==========

        if self.sensor_type in ("last_pour", "daily_consumed"):
            # always stay in oz here; display_* variants handle ml.
            try:
                raw_oz = float(raw)
            except (TypeError, ValueError):
                return None
            self._attr_native_unit_of_measurement = "oz"
            return round(raw_oz, 1)

        # all remaining fields just return their stored value
        self._attr_native_unit_of_measurement = self._meta.get("unit")
        return raw

    async def async_added_to_hass(self) -> None:
        """Subscribe to integration update events for this keg."""
        self.async_on_remove(
            self.hass.bus.async_listen(PLATFORM_EVENT, self._refresh_if_mine)
        )

    @callback
    def _refresh_if_mine(self, event) -> None:
        """Refresh state when our keg_id gets an update event."""
        if (event.data or {}).get("keg_id") == self.keg_id:
            # Recompute native_value + native_unit_of_measurement
            self.async_write_ha_state()
