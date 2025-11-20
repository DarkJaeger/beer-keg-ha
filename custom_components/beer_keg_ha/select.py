from __future__ import annotations

import logging
from typing import Any, Dict, List

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORM_EVENT = f"{DOMAIN}_update"
DEVICES_UPDATE_EVENT = f"{DOMAIN}_devices_update"

# Global unit selects for the integration
UNIT_SELECTS: Dict[str, Dict[str, Any]] = {
    "weight": {
        "name": "Keg Weight Unit",
        "options": ["kg", "lb"],
    },
    "temp": {
        "name": "Keg Temperature Unit",
        "options": ["°C", "°F"],
    },
    "pour": {
        "name": "Keg Volume Unit",
        "options": ["oz", "ml"],
    },
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up device + unit selects for the Beer Keg integration."""
    state = hass.data[DOMAIN][entry.entry_id]

    entities: List[SelectEntity] = []

    # 1) Device selector (select.keg_device)
    entities.append(BeerKegDeviceSelect(hass, entry, state))

    # 2) Global unit selectors (weight / temp / pour)
    for unit_kind in UNIT_SELECTS.keys():
        entities.append(BeerKegUnitSelect(hass, entry, unit_kind))

    async_add_entities(entities, True)


class BeerKegDeviceSelect(SelectEntity):
    """Select entity listing all keg devices discovered by the integration."""

    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        state_ref: Dict[str, Any],
    ) -> None:
        self.hass = hass
        self.entry = entry
        self._state_ref = state_ref

        # This will normally become entity_id: select.keg_device
        self._attr_name = "Keg Device"
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_keg_device"

        # store the last selected device in integration state
        if "selected_device" not in self._state_ref:
            self._state_ref["selected_device"] = None

    @property
    def device_info(self) -> DeviceInfo:
        """Group this under 'Beer Keg Settings'."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self.entry.entry_id}_settings")},
            name="Beer Keg Settings",
            manufacturer="Beer Keg",
            model="WebSocket + REST",
        )

    # ---- SelectEntity core ----

    @property
    def options(self) -> list[str]:
        """Return list of keg device IDs known by the integration."""
        devices = self._state_ref.get("devices") or []
        return list(devices)

    @property
    def current_option(self) -> str | None:
        """Current selected keg id."""
        selected = self._state_ref.get("selected_device")
        if selected in self.options:
            return selected
        # Fallback: first option if nothing selected yet
        if self.options:
            return self.options[0]
        return None

    async def async_select_option(self, option: str) -> None:
        """Handle user picking a keg from the dropdown."""
        if option not in self.options:
            _LOGGER.warning("%s: Attempt to select unknown keg device: %s", DOMAIN, option)
            return

        self._state_ref["selected_device"] = option
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Refresh when devices list changes."""

        @callback
        def _handle_devices_update(event) -> None:
            # A devices list update means our options may have changed
            self.async_write_ha_state()

        # Listen for /api/kegs/devices updates from __init__.py
        self.async_on_remove(
            self.hass.bus.async_listen(DEVICES_UPDATE_EVENT, _handle_devices_update)
        )


class BeerKegUnitSelect(SelectEntity):
    """Global select entity to control display units (weight/temp/pour)."""

    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        unit_kind: str,
    ) -> None:
        self.hass = hass
        self.entry = entry
        self._unit_kind = unit_kind  # "weight", "temp", or "pour"

        meta = UNIT_SELECTS[unit_kind]

        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_unit_{unit_kind}"
        self._attr_name = meta["name"]
        self._attr_options = meta["options"]

    @property
    def device_info(self) -> DeviceInfo:
        """Group unit selects under a shared 'Beer Keg Settings' device."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self.entry.entry_id}_settings")},
            name="Beer Keg Settings",
            manufacturer="Beer Keg",
            model="WebSocket + REST",
        )

    @property
    def current_option(self) -> str | None:
        """Return the currently selected option based on integration state."""
        domain_state = self.hass.data[DOMAIN][self.entry.entry_id]
        du = domain_state.get("display_units", {})

        if self._unit_kind == "weight":
            val = du.get("weight", "kg")
            return val if val in UNIT_SELECTS["weight"]["options"] else "kg"

        if self._unit_kind == "temp":
            val = du.get("temp", "°C")
            return val if val in UNIT_SELECTS["temp"]["options"] else "°C"

        # pour / volume
        val = du.get("pour", "oz")
        return val if val in UNIT_SELECTS["pour"]["options"] else "oz"

    async def async_select_option(self, option: str) -> None:
        """Handle user selecting a new option."""
        domain_state = self.hass.data[DOMAIN][self.entry.entry_id]

        if option not in self._attr_options:
            _LOGGER.warning(
                "%s: Invalid option '%s' for %s",
                DOMAIN,
                option,
                self._unit_kind,
            )
            return

        du = domain_state.setdefault("display_units", {})

        if self._unit_kind == "weight":
            du["weight"] = option
        elif self._unit_kind == "temp":
            du["temp"] = option
        else:  # pour
            du["pour"] = option

        # Persist preferences if prefs_store exists
        prefs_store = domain_state.get("prefs_store")
        if prefs_store is not None:
            await prefs_store.async_save({"display_units": du})

        # Notify all keg sensors so they recalc units
        for keg_id in list(domain_state.get("data", {}).keys()):
            self.hass.bus.async_fire(
                PLATFORM_EVENT,
                {"keg_id": keg_id},
            )

        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Refresh when integration fires update events."""

        @callback
        def _handle_update(event) -> None:
            # If display units change from somewhere else, refresh our select
            self.async_write_ha_state()

        self.async_on_remove(
            self.hass.bus.async_listen(PLATFORM_EVENT, _handle_update)
        )
