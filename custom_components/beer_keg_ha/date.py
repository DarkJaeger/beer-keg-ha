from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, List, Set

from homeassistant.components.date import DateEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORM_EVENT = f"{DOMAIN}_update"


def _short_keg_id(keg_id: str) -> str:
    """Short human-friendly ID (first 4 chars)."""
    keg_id = str(keg_id)
    if len(keg_id) <= 4:
        return keg_id
    return keg_id[:4]


DATE_FIELDS = {
    "kegged_date": {
        "name": "Kegged Date",
        "key": "kegged_date",
    },
    "expires_date": {
        "name": "Expiration Date",
        "key": "expires_date",
    },
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up date entities (kegged/expiration) per keg."""
    state = hass.data[DOMAIN][entry.entry_id]
    created: Set[str] = state.setdefault("created_date_kegs", set())

    def create_for(keg_id: str) -> None:
        if keg_id in created:
            return

        entities: List[BeerKegDateEntity] = [
            BeerKegDateEntity(hass, entry, keg_id, field_id)
            for field_id in DATE_FIELDS.keys()
        ]
        async_add_entities(entities, True)
        created.add(keg_id)

    # Create for any kegs we already know
    for keg_id in list(state.get("data", {}).keys()):
        create_for(keg_id)

    @callback
    def _on_update(event) -> None:
        """Create entities when a new keg shows up."""
        keg_id = (event.data or {}).get("keg_id")
        if keg_id:
            create_for(keg_id)

    entry.async_on_unload(
        hass.bus.async_listen(PLATFORM_EVENT, _on_update)
    )


class BeerKegDateEntity(DateEntity):
    """Date entity for kegged/expiration dates."""

    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        keg_id: str,
        field_id: str,
    ) -> None:
        self.hass = hass
        self.entry = entry
        self.keg_id = keg_id
        self._state_ref: Dict[str, Any] = hass.data[DOMAIN][entry.entry_id]

        meta = DATE_FIELDS[field_id]
        self._field_key = meta["key"]

        short_id = _short_keg_id(keg_id)

        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_{keg_id}_{self._field_key}"
        self._attr_name = f"Keg {short_id} {meta['name']}"

    @property
    def device_info(self) -> DeviceInfo:
        short_id = _short_keg_id(self.keg_id)
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self.entry.entry_id}_{self.keg_id}")},
            name=f"Beer Keg {short_id}",
            manufacturer="Beer Keg",
            model="WebSocket + REST",
        )

    @property
    def native_value(self) -> date | None:
        """Return current date from integration state (stored as ISO string)."""
        data: Dict[str, Dict[str, Any]] = self._state_ref.get("data", {})
        keg = data.get(self.keg_id, {})
        raw = keg.get(self._field_key)
        if not raw:
            return None

        try:
            return date.fromisoformat(str(raw))
        except Exception:
            return None

    async def async_set_value(self, value: date | None) -> None:
        """Update date in integration state."""
        domain_state = self._state_ref
        data: Dict[str, Dict[str, Any]] = domain_state.setdefault("data", {})
        keg = data.setdefault(self.keg_id, {})

        if value is None:
            # Clearing the date
            keg.pop(self._field_key, None)
        else:
            # Store as ISO string YYYY-MM-DD
            keg[self._field_key] = value.isoformat()

        # Let other entities/cards update
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
