# VCQtdb — Qt/C++ dashboard (VS Code)

A C++/Qt6 desktop dashboard for the Unified Flight Tracker backend.
Same layout and semantics as the PyQt version, implemented in C++ with
CMake and Qt Widgets. VS Code integration is provided under `.vscode/`.

## Layout

- **KPI bar** — connection LED, backend latency, aircraft count, closest, highest.
- **Polar sky view** — radar-style plot. Azimuth 0° = North (up), elevation 90° at center, horizon on the outer ring; below-horizon aircraft appear dimmed on an outer band. Dots pulse briefly after each track refresh; color is altitude-banded. Click a dot to select.
- **Flight table** — sortable, filterable `QTableView` with numeric-aware sort and monospace right-aligned numbers.
- **Altitude strip chart** — 5-minute rolling window in a bottom dock. Blue band = fleet altitude envelope. Cyan trace = selected aircraft.

## Install (Linux)

```
./install.sh
```

Installs Qt6 (Base + Widgets + Network) plus CMake/Ninja/GCC via the
platform package manager (apt / dnf / pacman), then configures and
builds the project into `./build/vcqtdb`.

## Build manually

```
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build --parallel
./build/vcqtdb --url http://localhost:5001
```

## VS Code

Open the folder in VS Code — the recommended extensions
(`ms-vscode.cpptools`, `ms-vscode.cmake-tools`, `tonka3000.qtvsctools`)
are suggested via `.vscode/extensions.json`. Tasks and a debug launch
config are provided:

- `Ctrl+Shift+B` — configure + build via Ninja.
- `F5` — build then launch `vcqtdb` under `gdb`.

CMake writes `compile_commands.json` into `build/`, which the C/C++
extension consumes automatically.

## Options

Same as the PyQt version — pass `--url`, `--lat`, `--lon`, `--radius`,
`--interval`, or set `TRACKER_URL`, `TRACKER_LAT`, `TRACKER_LON`,
`TRACKER_RADIUS`, `TRACKER_INTERVAL`.
