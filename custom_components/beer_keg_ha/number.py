from __future__ import annotations

import logging
from typing import Any, Dict, List, Set

from homeassistant.components.number import (
    NumberEntity,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORM_EVENT = f"{DOMAIN}_update"

# We define 3 number types per keg:
#  - full_weight_kg
#  - weight_calibrate
#  - temp_calibrate_c
NUMBER_TYPES = {
    "full_weight_kg": {
        "name": "Full Weight (kg)",
        "key": "full_weight",
        "min": 0.0,
        "max": 100.0,
        "step": 0.01,
        "mode": NumberMode.BOX,
    },
    "weight_calibrate": {
        "name": "Weight Calibrate",
        "key": "weight_calibrate",
        "min": -10.0,
        "max": 10.0,
        "step": 0.01,
        "mode": NumberMode.BOX,
    },
    "temp_calibrate_c": {
        "name": "Temp Calibrate (°C)",
        "key": "temperature_calibrate",
        "min": -10.0,
        "max": 10.0,
        "step": 0.1,
        "mode": NumberMode.BOX,
    },
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up keg calibration numbers from a config entry."""
    state = hass.data[DOMAIN][entry.entry_id]
    created: Set[str] = state.setdefault("created_number_kegs", set())

    def create_for(keg_id: str) -> None:
        if keg_id in created:
            return

        entities: List[BeerKegNumberEntity] = []
        for num_type in NUMBER_TYPES.keys():
            entities.append(
                BeerKegNumberEntity(hass, entry, keg_id, num_type)
            )

        async_add_entities(entities, True)
        created.add(keg_id)

    # Create numbers for any kegs we already know about
    for keg_id in list(state.get("data", {}).keys()):
        create_for(keg_id)

    @callback
    def _on_update(event) -> None:
        """Create entities for new kegs when they appear."""
        keg_id = (event.data or {}).get("keg_id")
        if keg_id:
            create_for(keg_id)

    entry.async_on_unload(
        hass.bus.async_listen(PLATFORM_EVENT, _on_update)
    )


class BeerKegNumberEntity(NumberEntity):
    """Number entity representing calibration/config values per keg."""

    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        keg_id: str,
        num_type: str,
    ) -> None:
        self.hass = hass
        self.entry = entry
        self.keg_id = keg_id
        self.num_type = num_type

        meta = NUMBER_TYPES[num_type]
        self._key = meta["key"]

        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_{keg_id}_{num_type}"
        self._attr_name = f"Keg {keg_id} {meta['name']}"
        self._attr_mode = meta["mode"]
        self._attr_native_min_value = meta["min"]
        self._attr_native_max_value = meta["max"]
        self._attr_native_step = meta["step"]
        self._attr_native_unit_of_measurement = "kg" if self._key in ("full_weight", "weight_calibrate") else "°C"

    @property
    def device_info(self) -> DeviceInfo:
        """Attach these numbers to the keg device."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self.entry.entry_id}_{self.keg_id}")},
            name=f"Beer Keg {self.keg_id}",
            manufacturer="Beer Keg",
            model="WebSocket + REST",
        )

    @property
    def native_value(self) -> float | None:
        """Return the current value from integration state."""
        data: Dict[str, Dict[str, Any]] = self.hass.data[DOMAIN][self.entry.entry_id]["data"]
        keg = data.get(self.keg_id, {})
        val = keg.get(self._key)
        if val is None:
            return None
        try:
            return float(val)
        except (TypeError, ValueError):
            return None

    async def async_set_native_value(self, value: float) -> None:
        """Update the value in integration state (does NOT call REST yet)."""
        domain_state = self.hass.data[DOMAIN][self.entry.entry_id]
        data: Dict[str, Dict[str, Any]] = domain_state.setdefault("data", {})
        keg = data.setdefault(self.keg_id, {})
        keg[self._key] = float(value)

        # Let any listening sensors/cards update
        self.hass.bus.async_fire(
            f"{DOMAIN}_update",
            {"keg_id": self.keg_id},
        )
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Listen for integration updates and refresh."""
        @callback
        def _handle_update(event) -> None:
            if (event.data or {}).get("keg_id") == self.keg_id:
                self.async_write_ha_state()

        self.async_on_remove(
            self.hass.bus.async_listen(PLATFORM_EVENT, _handle_update)
        )