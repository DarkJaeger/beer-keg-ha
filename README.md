\# Beer Keg Scale (Home Assistant)



Live keg weight, temperature, fill %, pours, and history — with WebSocket + REST fallback. Supports density-aware fill% using Full Volume (L) and Beer SG.



\## Install (HACS - Custom repo)

1\. HACS → Integrations → 3-dot menu → \*\*Custom repositories\*\*

2\. Add: `https://github.com/DarkJaeger/beer_keg_ha` as type \*\*Integration\*\*

3\. Search “Beer Keg Scale” → Install → \*\*Restart Home Assistant\*\*

4\. Settings → Devices \& Services → \*\*Add Integration\*\* → Beer Keg Scale



\## Configure

\- \*\*WebSocket URL\*\*: `ws://<host>:8085/ws`

\- Options:

&nbsp; - Empty keg weight (kg): `0` if you tare with empty keg

&nbsp; - Full volume (L): e.g. `19.0`

&nbsp; - Beer SG: e.g. `1.010` (defaults to typical finished beer)

&nbsp; - Default full weight (kg): fallback if needed

&nbsp; - Per-keg full weights JSON: `{ "keg\_id": 19.0 }`

\.Restart Home Assistant

\## Entities

\- `sensor.keg\_<id>\_weight` (kg)

\- `sensor.keg\_<id>\_temperature` (°C)

\- `sensor.keg\_<id>\_fill\_percent` (and legacy alias `\_fill\_level`)

\- `sensor.keg\_<id>\_last\_pour` (oz)

\- `sensor.keg\_<id>\_daily\_consumed` (oz)

\- `sensor.keg\_<id>\_full\_weight` (kg)

\- `sensor.keg\_<id>\_name`, `sensor.keg\_<id>\_id`



\## Services

\- `beer\_keg\_ha.export\_history`

\- `beer\_keg\_ha.refresh\_kegs`



\## Notes

\- WS for realtime, REST poll + watchdog for resilience.

\- Fill% chooses full\_weight: device → per-keg override → `volume × SG × 0.998` → default.

\- Example yaml for Lovelace card to display keg information
\-   type: vertical-stack
\-cards:
\-  - type: entities
\-    title: 🍺 Tap 1 Status
\-    entities:
\-      - entity: sensor.keg_\_<id>\_weight_display
\-        name: Current Weight
\-        icon: mdi:scale
\-      - entity: sensor.keg_\_<id>\_fill_level
\-        name: Fill Level
\-        icon: mdi:beer
\-      - entity: sensor.keg_\_<id>\_temperature_display
\-        name: Temperature
\-        icon: mdi:thermometer
\-      - entity: sensor.keg_\_<id>\_last_pour
\-        name: Last Pour
\-        icon: mdi:cup
\-      - entity: sensor.keg_\_<id>\_daily_consumption
\-        name: Daily Consumption
\-        icon: mdi:calendar-today
\-      - entity: sensor.keg_\_<id>\_name
\-        name: TAP1
\-  - type: gauge
\-    entity: sensor.keg_\_<id>\_fill_level
\-    name: Tap1 Fill %
\-    min: 0
\-    max: 100
\-    severity:
\-      green: 50
\-      yellow: 25
\-      red: 10
\-  - type: history-graph
\-    title: Tap1 – Last 24h
\-    hours_to_show: 24
\-    entities:
\-      - entity: sensor.keg_\_<id>\_weight
\-        name: Weight
\-      - entity: sensor.keg_\_<id>\_daily_consumption
\-        name: Daily Consumption

\- Example2 yaml for Lovelace card to display keg information (keg that fills with the level of the weight)
\-  type: custom:button-card
\-entity: sensor.keg_d00dcafe5ded57971fce7ec1b3ff4253_fill_level
\-show_icon: false
\-show_name: false
\-show_state: false
\-styles:
\-  card:
\-    - width: 180px
\-    - height: 380px
\-    - padding: 0
\-    - border-radius: 16px
\-    - background: "#1c1c1c"
\-    - box-shadow: 0 6px 18px rgba(0,0,0,0.35)
\-  custom_fields:
\-    keg:
\-      - position: absolute
\-      - inset: 0
\-      - display: flex
\-      - align-items: center
\-      - justify-content: center
\-custom_fields:
\-  keg: >-
\-    [[[ const pct = entity && entity.state ? Math.max(0, Math.min(100,
\-    parseFloat(entity.state))) : 0; const IX=44,IY=56,IW=112,IH=388; const
\-    h=Math.round((pct/100)*IH); const y=IY+IH-h; const
\-    color=pct>50?"#00c66a":(pct>20?"#ffcc00":"#ff4545"); return `<svg viewBox="0
\-    0 200 500" width="160" height="400"
\-    xmlns="http://www.w3.org/2000/svg"><defs><clipPath id="k"><rect x="${IX}"
\-    y="${IY}" width="${IW}" height="${IH}" rx="12"
\-    ry="12"/></clipPath><linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop
\-    offset="0%" stop-color="${color}" stop-opacity="0.95"/><stop offset="100%"
\-    stop-color="#3b2f1f" stop-opacity="0.85"/></linearGradient></defs><rect
\-    x="40" y="20" width="120" height="460" rx="20" ry="20" fill="none"
\-    stroke="#b3b3b3" stroke-width="8"/><rect x="35" y="20" width="130"
\-    height="32" rx="16" ry="16" fill="none" stroke="#b3b3b3"
\-    stroke-width="6"/><rect x="35" y="448" width="130" height="32" rx="16"
\-    ry="16" fill="none" stroke="#b3b3b3" stroke-width="6"/><rect x="${IX}"
\-    y="${y}" width="${IW}" height="${h}" clip-path="url(#k)"
\-    fill="url(#g)"/><text x="100" y="260" text-anchor="middle" fill="#ffffff"
\-    font-size="28"
\-    font-weight="700">${isFinite(pct)?Math.round(pct):"—"}%</text></svg>`; ]]]

\- Yaml code for creating card to set full weight, weight cal,temp and set display units
\-type: vertical-stack
\-cards:
\-  - type: markdown
\-    content: |
\-      ## 🍺 Keg Calibration & Units
\-      Select a keg, edit values, and save.
\-  - type: entities
\-    entities:
\-      - entity: select.keg_device
\-        name: Keg ID
\-      - entity: input_text.beer_keg_name
\-        name: Keg Name
\-      - entity: input_number.keg_cfg_full_weight_kg
\-        name: Full weight (kg)
\-      - entity: input_number.keg_cfg_weight_cal
\-        name: Weight calibrate
\-      - entity: input_number.keg_cfg_temp_cal_c
\-        name: Temp calibrate (°C)
\-      - type: divider
\-      - entity: select.keg_weight_unit
\-        name: Display weight unit
\-      - entity: select.keg_temperature_unit
\-        name: Display temperature unit
\-  - type: horizontal-stack
\-    cards:
\-      - show_name: true
\-        show_icon: true
\-        type: button
\-        name: Save calibration
\-        icon: mdi:content-save
\-        tap_action:
\-          action: call-service
\-          service: beer_keg_ha.calibrate_keg
\-          data:
\-            id: "{{ states('input_text.keg_cfg_id') }}"
\-            name: "{{ states('input_text.keg_cfg_name') }}"
\-            full_weight: "{{ states('input_number.keg_cfg_full_weight_kg') | float(0) }}"
\-            weight_calibrate: "{{ states('input_number.keg_cfg_weight_cal') | float(0) }}"
\-            temperature_calibrate: "{{ states('input_number.keg_cfg_temp_cal_c') | float(0) }}"
\-      - type: button
\-        name: Apply units
\-        icon: mdi:tune-vertical
\-        tap_action:
\-          action: call-service
\-          service: beer_keg_ha.set_display_units
\-      - type: button
\-        name: Refresh
\-        icon: mdi:refresh
\-        tap_action:
\-          action: call-service
\-          service: beer_keg_ha.refresh_kegs

\Trouble shooting

\Clear HACS cache before retry

\In Home Assistant:

1.\HACS → ⋯ menu → Clear downloads

2.\HACS → ⋯ menu → Reload data

3.\If still cached: restart Home Assistant

4.\Try the install again

