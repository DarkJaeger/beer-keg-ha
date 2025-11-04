from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, CONF_WS_URL

STEP_USER_DATA_SCHEMA = vol.Schema({vol.Required(CONF_WS_URL): str})

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        if user_input is not None:
            # single-instance per ws_url
            await self.async_set_unique_id(user_input[CONF_WS_URL])
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title="Beer Keg Scale", data=user_input)
        return self.async_show_form(step_id="user", data_schema=STEP_USER_DATA_SCHEMA)

    async def async_step_import(self, user_input=None):
        # Optional: support YAML import
        return await self.async_step_user(user_input)

class OptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        data = self.config_entry.options or {}
        schema = vol.Schema({
            vol.Optional("empty_weight", default=data.get("empty_weight", 4.0)): float,
            vol.Optional("default_full_weight", default=data.get("default_full_weight", 19.0)): float,
            vol.Optional("pour_threshold", default=data.get("pour_threshold", 0.15)): float,
            vol.Optional("per_keg_full", default=data.get("per_keg_full", "{}")): str,
        })
        return self.async_show_form(step_id="init", data_schema=schema)

async def async_get_options_flow(config_entry):
    return OptionsFlowHandler(config_entry)
