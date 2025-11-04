from __future__ import annotations

import logging
from typing import Any, Dict, List, Set

from homeassistant.core import callback, HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORM_EVENT = f"{DOMAIN}_update"

# Sensor type definitions
SENSOR_TYPES = {
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
    "fill_percent": {
        "unit": "%",
        "name": "Fill Level",
        "key": "fill_percent",
        "icon": "mdi:cup",
        "device_class": None,
        "state_class": "measurement",
    },
    "last_pour": {
        "unit": "oz",  # ounces
        "name": "Last Pour",
        "key": "last_pour",
        "icon": "mdi:cup-water",
        "device_class": None,
        "state_class": "measurement",
    },
    "daily_consumed": {
        "unit": "oz",  # ounces
        "name": "Daily Consumption",
        "key": "daily_consumed",
        "icon": "mdi:beer",
        "device_class": None,
        "state_class": "total_increasing",
    },
    "full_weight": {
        "unit": "kg",
        "name": "Full Weight",
        "key": "full_weight",
        "icon": "mdi:weight",
        "device_class": "weight",
        "state_class": "measurement",
    },
    # ✅ Text sensors (no unit/device_class/state_class)
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

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up keg sensors when the integration entry is loaded."""
    state = hass.data[DOMAIN][entry.entry_id]
    state.setdefault("created_kegs", set())
    created: Set[str] = state["created_kegs"]

    def _create_entities_for(keg_id: str) -> None:
        if keg_id in created:
            return
        entities: List[KegSensor] = []
        for st_key in SENSOR_TYPES.keys():
            entities.append(KegSensor(hass, entry, keg_id, st_key))
        async_add_entities(entities, True)
        created.add(keg_id)
        _LOGGER.debug("Beer Keg: created %d sensor entities for keg_id=%s", len(entities), keg_id)

    # Create entities for existing kegs (REST discovery may have populated already)
    for keg_id in list(state.get("data", {}).keys()):
        _create_entities_for(keg_id)

    # Listen for future updates to add new kegs dynamically
    @callback
    def _handle_update(event) -> None:
        keg_id = (event.data or {}).get("keg_id")
        if not keg_id:
            return
        _create_entities_for(keg_id)

    entry.async_on_unload(hass.bus.async_listen(PLATFORM_EVENT, _handle_update))


class KegSensor(SensorEntity):
    """Per-keg sensor that reads from the integration's shared store."""
    _attr_should_poll = False

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, keg_id: str, sensor_type: str) -> None:
        self.hass = hass
        self.entry = entry
        self.keg_id = keg_id
        self.sensor_type = sensor_type

        meta = SENSOR_TYPES[sensor_type]
        self._attr_name = f"Keg {keg_id} {meta['name']}"
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_{keg_id}_{sensor_type}"
        self._attr_icon = meta.get("icon")
        self._attr_device_class = meta.get("device_class")
        self._attr_state_class = meta.get("state_class")
        self._attr_native_unit_of_measurement = meta.get("unit")

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self.entry.entry_id}_{self.keg_id}")},
            name=f"Beer Keg {self.keg_id}",
            manufacturer="Beer Keg",
            model="WebSocket + REST",
        )

    @property
    def native_value(self) -> Any:
        data: Dict[str, Dict[str, Any]] = self.hass.data[DOMAIN][self.entry.entry_id]["data"]
        meta = SENSOR_TYPES[self.sensor_type]
        return data.get(self.keg_id, {}).get(meta["key"])

    async def async_added_to_hass(self) -> None:
        # Refresh when this keg updates
        self.async_on_remove(
            self.hass.bus.async_listen(PLATFORM_EVENT, self._refresh_if_mine)
        )

    @callback
    def _refresh_if_mine(self, event) -> None:
        if (event.data or {}).get("keg_id") == self.keg_id:
            self.async_write_ha_state()
