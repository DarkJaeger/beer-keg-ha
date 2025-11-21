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

# Per-keg text fields we expose:
#  - name              (display name)
#  - beer_sg           (current / target SG)
#  - original_gravity  (OG)
TEXT_TYPES: Dict[str, Dict[str, Any]] = {
    "name": {
        "key": "name",
        "name": "Keg Name",
        "min": 0,
        "max": 64,
    },
    "beer_sg": {
        "key": "beer_sg",
        "name": "Beer SG",
        "min": 0,
        "max": 16,
    },
    "original_gravity": {
        "key": "original_gravity",
        "name": "Original Gravity",
        "min": 0,
        "max": 16,
    },
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up per-keg text entities (name / SG / OG)."""
    state = hass.data[DOMAIN][entry.entry_id]
    created: Set[str] = state.setdefault("created_text_kegs", set())

    entities: List[TextEntity] = []

    def create_for(keg_id: str) -> None:
        if keg_id in created:
            return
        for text_type in TEXT_TYPES.keys():
            entities.append(BeerKegTextEntity(hass, entry, keg_id, text_type))
        created.add(keg_id)

    # Existing kegs
    for keg_id in list(state.get("data", {}).keys()):
        create_for(keg_id)

    async_add_entities(entities, True)

    @callback
    def _on_update(event) -> None:
        """Create entities when new kegs appear."""
        keg_id = (event.data or {}).get("keg_id")
        if keg_id and keg_id not in created:
            new_ents: List[TextEntity] = []
            for text_type in TEXT_TYPES.keys():
                new_ents.append(BeerKegTextEntity(hass, entry, keg_id, text_type))
            created.add(keg_id)
            async_add_entities(new_ents, True)

    entry.async_on_unload(
        hass.bus.async_listen(PLATFORM_EVENT, _on_update)
    )


class BeerKegTextEntity(TextEntity):
    """Per-keg text entity backed by integration state + prefs_store."""

    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        keg_id: str,
        text_type: str,
    ) -> None:
        self.hass = hass
        self.entry = entry
        self.keg_id = keg_id
        self.text_type = text_type

        self._state_ref: Dict[str, Any] = hass.data[DOMAIN][entry.entry_id]
        meta = TEXT_TYPES[text_type]
        self._key = meta["key"]

        short_id = keg_id[:4]

        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_{keg_id}_text_{text_type}"
        self._attr_name = f"Keg {short_id} {meta['name']}"
        self._attr_mode = "text"
        self._attr_min = meta["min"]
        self._attr_max = meta["max"]

    @property
    def device_info(self) -> DeviceInfo:
        short_id = self.keg_id[:4]
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self.entry.entry_id}_{self.keg_id}")},
            name=f"Beer Keg {short_id}",
            manufacturer="Beer Keg",
            model="WebSocket + REST",
        )

    @property
    def native_value(self) -> str | None:
        """Return current text from keg_config (prefs), falling back to data."""
        domain_state = self._state_ref
        keg_cfg: Dict[str, Dict[str, Any]] = domain_state.setdefault("keg_config", {})
        cfg = keg_cfg.get(self.keg_id, {})

        if self._key == "name":
            # name: prefer config; fall back to live data; else keg_id
            if "name" in cfg and cfg["name"]:
                return str(cfg["name"])
            data = domain_state.get("data", {}).get(self.keg_id, {})
            if data.get("name"):
                return str(data["name"])
            return self.keg_id

        # SG / OG: just whatever is stored in config
        val = cfg.get(self._key)
        if val is None:
            return ""
        return str(val)

    async def async_set_value(self, value: str) -> None:
        """Update config, persist via prefs_store, and nudge sensors."""
        domain_state = self._state_ref
        keg_cfg: Dict[str, Dict[str, Any]] = domain_state.setdefault("keg_config", {})
        cfg = keg_cfg.setdefault(self.keg_id, {})

        # Simple bounds trimming
        meta = TEXT_TYPES[self.text_type]
        if value is None:
            value = ""
        value = str(value)
        if meta["max"] and len(value) > meta["max"]:
            value = value[: meta["max"]]

        cfg[self._key] = value

        # Mirror into data dict for convenience
        data = domain_state.setdefault("data", {})
        keg_data = data.setdefault(self.keg_id, {})
        keg_data[self._key] = value

        # Persist (along with display_units)
        prefs_store = domain_state.get("prefs_store")
        if prefs_store is not None:
            await prefs_store.async_save(
                {
                    "display_units": domain_state.get("display_units", {}),
                    "keg_config": keg_cfg,
                }
            )

        # Nudge sensors/cards
        self.hass.bus.async_fire(
            PLATFORM_EVENT,
            {"keg_id": self.keg_id},
        )
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Refresh when this keg is updated elsewhere."""
        @callback
        def _handle_update(event) -> None:
            if (event.data or {}).get("keg_id") == self.keg_id:
                self.async_write_ha_state()

        self.async_on_remove(
            self.hass.bus.async_listen(PLATFORM_EVENT, _handle_update)
        )
