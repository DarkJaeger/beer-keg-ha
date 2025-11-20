from __future__ import annotations

import logging
from typing import Any, Dict, List, Set

from homeassistant.components.text import TextEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORM_EVENT = f"{DOMAIN}_update"


def _short_keg_id(keg_id: str) -> str:
    """Short human-friendly ID for UI naming (first 4 chars)."""
    keg_id = str(keg_id)
    if len(keg_id) <= 4:
        return keg_id
    return keg_id[:4]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up text entities (names) for each keg."""
    state = hass.data[DOMAIN][entry.entry_id]
    created: Set[str] = state.setdefault("created_text_kegs", set())

    def create_for(keg_id: str) -> None:
        if keg_id in created:
            return

        ent = BeerKegNameTextEntity(hass, entry, keg_id)
        async_add_entities([ent], True)
        created.add(keg_id)

    # Create for already-known kegs
    for keg_id in list(state.get("data", {}).keys()):
        create_for(keg_id)

    @callback
    def _on_update(event) -> None:
        """Create entities when new kegs appear."""
        keg_id = (event.data or {}).get("keg_id")
        if keg_id:
            create_for(keg_id)

    entry.async_on_unload(
        hass.bus.async_listen(PLATFORM_EVENT, _on_update)
    )


class BeerKegNameTextEntity(TextEntity):
    """Text entity representing the keg name."""

    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        keg_id: str,
    ) -> None:
        self.hass = hass
        self.entry = entry
        self.keg_id = keg_id

        self._state_ref: Dict[str, Any] = hass.data[DOMAIN][entry.entry_id]

        short_id = _short_keg_id(keg_id)

        # Unique ID uses full keg_id to avoid collisions
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_{keg_id}_name"
        # Friendly name uses short ID
        self._attr_name = f"Keg {short_id} Name"

        # Optional: limit length, etc.
        self._attr_min_length = 0
        self._attr_max_length = 64

    @property
    def device_info(self) -> DeviceInfo:
        """Attach to the same keg device as sensors/numbers."""
        short_id = _short_keg_id(self.keg_id)
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self.entry.entry_id}_{self.keg_id}")},
            name=f"Beer Keg {short_id}",
            manufacturer="Beer Keg",
            model="WebSocket + REST",
        )

    @property
    def native_value(self) -> str | None:
        """Read the current keg name from integration state."""
        data: Dict[str, Dict[str, Any]] = self._state_ref.get("data", {})
        keg = data.get(self.keg_id, {})
        name = keg.get("name")
        if not name:
            # Fallback to keg_id if no name set
            return self.keg_id
        return str(name)

    async def async_set_value(self, value: str) -> None:
        """Update the keg name in integration state (no REST yet)."""
        value = str(value).strip()
        domain_state = self._state_ref
        data: Dict[str, Dict[str, Any]] = domain_state.setdefault("data", {})
        keg = data.setdefault(self.keg_id, {})

        # Update name in memory
        keg["name"] = value or self.keg_id

        # Fire update so any sensors/cards can pick up the new name
        self.hass.bus.async_fire(
            f"{DOMAIN}_update",
            {"keg_id": self.keg_id},
        )
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Refresh when this keg gets new data."""
        @callback
        def _handle_update(event) -> None:
            if (event.data or {}).get("keg_id") == self.keg_id:
                self.async_write_ha_state()

        self.async_on_remove(
            self.hass.bus.async_listen(PLATFORM_EVENT, _handle_update)
        )
