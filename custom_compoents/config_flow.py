from __future__ import annotations

import json
import voluptuous as vol
from typing import Any, Dict, Optional
from homeassistant import config_entries
from homeassistant.core import callback

from .const import (
    DOMAIN,
    CONF_WS_URL,
    CONF_EMPTY_WEIGHT,
    CONF_DEFAULT_FULL_WEIGHT,
    CONF_POUR_THRESHOLD,
    CONF_PER_KEG_FULL,
    DEFAULT_EMPTY_WEIGHT,
    DEFAULT_FULL_WEIGHT,
    DEFAULT_POUR_THRESHOLD,
    DEFAULT_PER_KEG_FULL_JSON,
)

DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_WS_URL): str,
})

def _options_schema(current: Dict[str, Any]) -> vol.Schema:
    return vol.Schema({
        vol.Required(CONF_EMPTY_WEIGHT, default=current.get(CONF_EMPTY_WEIGHT, DEFAULT_EMPTY_WEIGHT)): vol.Coerce(float),
        vol.Required(CONF_DEFAULT_FULL_WEIGHT, default=current.get(CONF_DEFAULT_FULL_WEIGHT, DEFAULT_FULL_WEIGHT)): vol.Coerce(float),
        vol.Required(CONF_POUR_THRESHOLD, default=current.get(CONF_POUR_THRESHOLD, DEFAULT_POUR_THRESHOLD)): vol.Coerce(float),
        vol.Optional(
            CONF_PER_KEG_FULL,
            description="JSON mapping of keg_id -> full_weight, e.g. {\"keg1\": 19, \"keg2\": 30}",
            default=current.get(CONF_PER_KEG_FULL, DEFAULT_PER_KEG_FULL_JSON)
        ): str,
    })

class BeerKegConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None):
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA)

        # prevent duplicates (single instance)
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title="Beer Keg",
            data={
                CONF_WS_URL: user_input[CONF_WS_URL]
            },
            options={
                CONF_EMPTY_WEIGHT: DEFAULT_EMPTY_WEIGHT,
                CONF_DEFAULT_FULL_WEIGHT: DEFAULT_FULL_WEIGHT,
                CONF_POUR_THRESHOLD: DEFAULT_POUR_THRESHOLD,
                CONF_PER_KEG_FULL: DEFAULT_PER_KEG_FULL_JSON,
            }
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return BeerKegOptionsFlowHandler(config_entry)

class BeerKegOptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input: Optional[Dict[str, Any]] = None):
        if user_input is not None:
            # Validate the JSON mapping (if provided)
            mapping = user_input.get(CONF_PER_KEG_FULL, DEFAULT_PER_KEG_FULL_JSON)
            try:
                if mapping.strip():
                    json.loads(mapping)
            except Exception as e:
                return self.async_show_form(
                    step_id="init",
                    data_schema=_options_schema(self.config_entry.options),
                    errors={"base": f"invalid_json: {e}"}
                )

            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=_options_schema(self.config_entry.options)
        )
