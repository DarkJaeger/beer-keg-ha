from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.components.persistent_notification import async_create as pn_create
from homeassistant.helpers.storage import Store

from .const import (
    DOMAIN,
    CONF_WS_URL,
    CONF_EMPTY_WEIGHT,
    CONF_DEFAULT_FULL_WEIGHT,
    CONF_POUR_THRESHOLD,
    CONF_PER_KEG_FULL,
    MAX_LOG_ENTRIES,
    DEFAULT_EMPTY_WEIGHT,
    DEFAULT_FULL_WEIGHT,
    DEFAULT_POUR_THRESHOLD,
)

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["sensor"]

KG_TO_OZ = 35.274  # Conversion constant


def _coerce_float(val, default=0.0):
    try:
        return float(val)
    except Exception:
        return default


def _normalize_keg_dict(keg: dict) -> dict:
    """Normalize keg data from REST or WebSocket payloads."""
    keg_id = str(keg.get("id", "unknown")).lower().replace(" ", "_")
    weight = _coerce_float(keg.get("weight"))
    temp = keg.get("temperature")
    temp = _coerce_float(temp) if temp is not None else None
    full_w = _coerce_float(keg.get("full_weight"), default=0.0)
    name = keg.get("name") or keg_id
    return {
        "keg_id": keg_id,
        "name": name,
        "weight": weight,
        "temperature": temp,
        "full_weight": full_w if full_w > 0 else None,
        "weight_calibrate": _coerce_float(keg.get("weight_calibrate")),
        "temperature_calibrate": _coerce_float(keg.get("temperature_calibrate")),
    }


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    try:
        ws_url: str = entry.data.get(CONF_WS_URL)
        if not ws_url:
            _LOGGER.error("beer_keg: Missing ws_url")
            return False

        opts = entry.options or {}
        empty_weight = float(opts.get(CONF_EMPTY_WEIGHT, DEFAULT_EMPTY_WEIGHT))
        default_full = float(opts.get(CONF_DEFAULT_FULL_WEIGHT, DEFAULT_FULL_WEIGHT))
        pour_threshold = float(opts.get(CONF_POUR_THRESHOLD, DEFAULT_POUR_THRESHOLD))

        per_keg_full: Dict[str, float] = {}
        raw_mapping = opts.get(CONF_PER_KEG_FULL)
        if raw_mapping:
            try:
                per_keg_full = {
                    str(k).lower().replace(" ", "_"): float(v)
                    for k, v in json.loads(raw_mapping).items()
                }
            except Exception as e:
                _LOGGER.warning("beer_keg: Invalid per_keg_full mapping: %s", e)

        hass.data.setdefault(DOMAIN, {})
        store: Store = Store(hass, 1, f"{DOMAIN}_history")
        hass.data[DOMAIN][entry.entry_id] = state = {
            "ws_url": ws_url,
            "empty_weight": empty_weight,
            "default_full": default_full,
            "pour_threshold": pour_threshold,
            "per_keg_full": per_keg_full,
            "kegs": {},
            "data": {},
            "history": [],
            "store": store,
        }

        loaded = await store.async_load()
        if isinstance(loaded, list):
            state["history"] = loaded
            _LOGGER.info("beer_keg: Loaded %d pour records", len(state["history"]))

        # ----- REST fetch -----
        import aiohttp
        from urllib.parse import urlparse, urlunparse

        async def fetch_kegs() -> List[Dict[str, Any]]:
            try:
                u = urlparse(ws_url)
                scheme = "http" if u.scheme == "ws" else "https" if u.scheme == "wss" else "http"
                base = urlunparse((scheme, u.netloc, "", "", "", ""))
                urls = [f"{base}/api/kegs", f"{base}/api/kegs/"]

                async with aiohttp.ClientSession() as session:
                    for url in urls:
                        try:
                            async with session.get(url) as resp:
                                if resp.status != 200:
                                    continue
                                data = await resp.json()
                                if isinstance(data, list):
                                    return data
                                if isinstance(data, dict) and isinstance(data.get("kegs"), list):
                                    return data["kegs"]
                        except Exception as e:
                            _LOGGER.warning("beer_keg: REST GET %s failed: %s", url, e)
                return []
            except Exception as e:
                _LOGGER.error("beer_keg: fetch_kegs error: %s", e)
                return []

        # ----- Update publisher -----
        async def _publish_keg(norm: dict):
            """Update state & fire update event."""
            keg_id = norm["keg_id"]
            weight = norm["weight"]
            temp = norm["temperature"]

            info = state["kegs"].get(keg_id)
            if not info:
                fw = norm["full_weight"] or per_keg_full.get(keg_id, default_full)
                info = state["kegs"][keg_id] = {
                    "last_weight": weight,
                    "daily_consumed": 0.0,
                    "last_pour": 0.0,
                    "last_pour_time": None,
                    "full_weight": float(fw),
                }

            if norm["full_weight"] and norm["full_weight"] > 0 and norm["full_weight"] != info["full_weight"]:
                info["full_weight"] = float(norm["full_weight"])

            prev_weight = info["last_weight"]
            info["last_weight"] = weight

            if prev_weight - weight > pour_threshold:
                pour_amt = round(prev_weight - weight, 2)
                pour_amt_oz = round(pour_amt * KG_TO_OZ, 1)
                info["last_pour"] = pour_amt_oz
                info["last_pour_time"] = datetime.now()
                info["daily_consumed"] += pour_amt_oz

                state["history"].append({
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "keg": keg_id,
                    "pour_oz": pour_amt_oz,
                    "weight_before": round(prev_weight, 2),
                    "weight_after": round(weight, 2),
                    "temperature": temp,
                })
                if len(state["history"]) > MAX_LOG_ENTRIES:
                    state["history"].pop(0)
                await store.async_save(state["history"][-MAX_LOG_ENTRIES:])
                _LOGGER.debug("beer_keg: pour %.1f oz on %s", pour_amt_oz, keg_id)

            fw = info["full_weight"]; ew = empty_weight
            fill_pct = max(0.0, min(100.0, ((weight - ew) / (fw - ew) * 100.0))) if fw > ew else 0.0

            state["data"][keg_id] = {
                "id": keg_id,
                "name": norm["name"],
                "weight": round(weight, 2),
                "temperature": round(temp, 1) if temp is not None else None,
                "full_weight": round(fw, 2),
                "daily_consumed": round(info["daily_consumed"], 1),
                "last_pour": round(info["last_pour"], 1),
                "fill_percent": round(fill_pct, 1),
            }
            hass.bus.async_fire(f"{DOMAIN}_update", {"keg_id": keg_id})

        # ----- REST discovery -----
        keg_list = await fetch_kegs()
        for raw in keg_list:
            norm = _normalize_keg_dict(raw)
            await _publish_keg(norm)
        if not keg_list:
            _LOGGER.warning("beer_keg: No kegs found via REST API")

        # ----- WebSocket listener -----
        async def connect_websocket():
            async with aiohttp.ClientSession() as session:
                while True:
                    try:
                        _LOGGER.info("beer_keg: Connecting to %s", ws_url)
                        async with session.ws_connect(ws_url) as ws:
                            _LOGGER.info("beer_keg: Connected to WS")
                            async for msg in ws:
                                if msg.type != aiohttp.WSMsgType.TEXT:
                                    continue
                                try:
                                    data = json.loads(msg.data)
                                except json.JSONDecodeError:
                                    continue

                                kegs = data.get("kegs")
                                source = kegs if isinstance(kegs, list) else data if isinstance(data, list) else None
                                if not source:
                                    continue

                                for raw in source:
                                    norm = _normalize_keg_dict(raw)
                                    await _publish_keg(norm)
                    except Exception as e:
                        _LOGGER.error("beer_keg: WS error: %s", e)
                        await asyncio.sleep(10)

        async def rest_poll(now=None):
            try:
                new_kegs = await fetch_kegs()
                if not new_kegs:
                    return
                for raw in new_kegs:
                    norm = _normalize_keg_dict(raw)
                    await _publish_keg(norm)
            except Exception as e:
                _LOGGER.debug("beer_keg: REST poll error: %s", e)

        async_track_time_interval(hass, rest_poll, timedelta(seconds=10))

        async def reset_daily(now=None):
            for keg_id, info in state["kegs"].items():
                info["daily_consumed"] = 0.0
                if keg_id in state["data"]:
                    state["data"][keg_id]["daily_consumed"] = 0.0
                    hass.bus.async_fire(f"{DOMAIN}_update", {"keg_id": keg_id})
            _LOGGER.info("beer_keg: Daily reset complete")

        async_track_time_interval(hass, reset_daily, timedelta(days=1))

        async def export_history(call: ServiceCall):
            path = hass.config.path("www/beer_keg_history.json")

            def _write_export():
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(state["history"][-MAX_LOG_ENTRIES:], f, indent=2)

            await hass.async_add_executor_job(_write_export)
            pn_create(
                hass,
                'Beer Keg history exported.<br><a href="/local/beer_keg_history.json" target="_blank">Open</a>',
                title="Beer Keg Export",
            )

        hass.services.async_register(DOMAIN, "export_history", export_history)

        async def refresh_kegs(call: ServiceCall):
            new_kegs = await fetch_kegs()
            for raw in new_kegs:
                norm = _normalize_keg_dict(raw)
                await _publish_keg(norm)
            pn_create(hass, f"Refreshed {len(new_kegs)} kegs", title="Beer Keg Refresh")

        hass.services.async_register(DOMAIN, "refresh_kegs", refresh_kegs)

        async def on_stop(event):
            await store.async_save(state["history"][-MAX_LOG_ENTRIES:])

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, on_stop)
        hass.async_create_task(connect_websocket())
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

        _LOGGER.info("beer_keg: setup complete (REST + WS + oz units)")
        return True

    except Exception as e:
        _LOGGER.exception("beer_keg: setup_entry crashed: %s", e)
        return False


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    state = hass.data[DOMAIN].get(entry.entry_id)
    if not state:
        return True
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded
