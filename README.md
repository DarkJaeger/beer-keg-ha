What it does (keg weight, temp, fill %, pour detection, oz/kg choice).

Requirements (a running server with /ws and /api/kegs).

Install via HACS (preferred):

HACS → Integrations → 3-dot menu → Custom repositories → Add your repo URL as type Integration.

Search “Beer Keg Scale” → Install.

Restart HA → Settings → Devices & Services → Add Integration → “Beer Keg Scale”.

Manual install:

Download the latest Release ZIP.

Extract to /config/custom_components/beer_keg/.

Restart HA → Add Integration.

Configuration instructions (WS URL, options).

Services (beer_keg.export_history, beer_keg.refresh_kegs).

Troubleshooting (logs, event listening).