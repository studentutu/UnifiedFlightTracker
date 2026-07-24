# PyQTDB — PyQt6 dashboard

A live desktop dashboard for the Unified Flight Tracker backend.

## Layout

- **KPI bar** — connection LED, backend latency, aircraft count, closest aircraft, highest aircraft.
- **Polar sky view** — radar-style plot centered on the observer. Azimuth 0° is North (up), elevation 90° is at the center. Below-horizon aircraft appear dimmed on an outer band. Dots pulse when their track refreshes and are color-coded by altitude. Click a dot to select the aircraft.
- **Flight table** — filterable, sortable, selection-preserving table. Columns are formatted for scan-ability (right-aligned monospace numbers, close/far distance coloring, red for below-horizon elevation).
- **Altitude strip chart** — 5-minute rolling window. The soft blue band is the fleet altitude envelope; the cyan trace is the selected aircraft. Lives in a bottom dock so you can float or hide it.

## Install (Linux)

```
./install.sh
```

Creates a local `.venv`, installs `PyQt6` and `requests`, and writes a `run-dashboard.sh` shim.

## Run

```
./run-dashboard.sh --url http://localhost:5001
```

or

```
source .venv/bin/activate
python -m dashboard --lat 39.5478 --lon -76.1347 --radius 150 --interval 5
```

All options can also be set via `TRACKER_URL`, `TRACKER_LAT`, `TRACKER_LON`, `TRACKER_RADIUS`, `TRACKER_INTERVAL` env vars.
