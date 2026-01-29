# Unified Flight Tracker

A multi-source aviation tracking dashboard that fuses real-time ADS-B data from local receivers, FlightAware, and Flightradar24 into a single unified view.

## Overview

Unified Flight Tracker combines aircraft telemetry from multiple sources:

- **Local ADS-B Receivers** - Dump1090 (1090 MHz) and Dump978 (978 MHz UAT)
- **FlightAware AeroAPI** - Commercial flight tracking data
- **Flightradar24 API** - Global flight tracking data

The application uses smart deconfliction to merge duplicate aircraft detections and prioritizes local data for the lowest latency tracking.

## Supported Platforms

| Platform | Architecture | Deployment Mode |
|----------|--------------|-----------------|
| Raspberry Pi 5 | ARM64 (aarch64) | Local tracker with ADS-B receiver |
| Raspberry Pi 4 | ARM64/ARM32 | Local tracker with ADS-B receiver |
| Ubuntu 24.04 | x86_64 | Remote client connecting to RPi tracker |
| Other Linux | x86_64/ARM | Either mode depending on setup |

The application automatically detects the platform and configures optimal data source paths.

## Features

### Data Fusion
- Ingests data from local Dump1090/Dump978, FlightAware, and Flightradar24
- Normalizes all data into a common format
- Deduplicates aircraft using ICAO hex codes and spatial proximity (6 NM threshold)
- Prioritizes local data over remote API data

### Dashboard
- **Flight Table** - Sortable list showing callsign, altitude, speed, heading, distance, and bearing
- **Map View** - Google Maps display with aircraft icons, range rings, and observer position
- **Sky Map** - Polar plot showing aircraft positions relative to observer (azimuth/elevation)

### Tracking
- Real-time bearing and distance from observer location
- Elevation angle calculation for sky view
- Configurable range radius
- 10-second automatic refresh

## Installation

### Prerequisites

- Python 3.10 or later
- Network access to your ADS-B receiver (if running remotely)

### Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd UnifiedFlightTracker
```

2. Create and activate a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Start the application to generate the default configuration:
```bash
python3 app.py
```

5. Edit `config.yaml` with your settings (see Configuration below).

6. Restart the application:
```bash
python3 app.py
```

7. Open your browser to `http://localhost:5000`

## Configuration

The application creates `config.yaml` on first run. Edit this file to configure your deployment.

### Basic Configuration

```yaml
api_keys:
  flightaware: "YOUR_FLIGHTAWARE_API_KEY"
  flightradar24: "YOUR_FR24_API_TOKEN"
  google_maps: "YOUR_GOOGLE_MAPS_API_KEY"

observer:
  latitude: 39.0
  longitude: -75.0
  altitude_m: 0
  radius_nm: 50

server:
  host: "0.0.0.0"
  port: 5000
```

### Local Sources Configuration

The `local_sources` section controls how the application connects to ADS-B receivers.

#### Running on the Raspberry Pi (Local Mode)

When running directly on the RPi with the ADS-B receiver attached:

```yaml
local_sources:
  tracker_host: "localhost"
  dump1090: ""
  dump978: ""
```

With empty values, the application auto-detects the best source:
1. Tries local file path (`/run/dump1090-fa/aircraft.json`)
2. Falls back to HTTP (`http://localhost:8080/data/aircraft.json`)

#### Running on a Remote Machine (Remote Mode)

When running on a separate computer (e.g., Ubuntu desktop) accessing an RPi tracker over the network:

```yaml
local_sources:
  tracker_host: "192.168.1.100"  # IP address of your Raspberry Pi
  dump1090: ""
  dump978: ""
```

The application connects via HTTP to the specified IP address.

#### Using Custom Endpoints

For non-standard setups, specify explicit paths or URLs:

```yaml
local_sources:
  tracker_host: "localhost"  # Ignored when explicit values are set
  dump1090: "http://192.168.1.100:8080/data/aircraft.json"
  dump978: "http://192.168.1.100:8978/data/aircraft.json"
```

Or use local file paths:

```yaml
local_sources:
  tracker_host: "localhost"
  dump1090: "/run/readsb/aircraft.json"
  dump978: "/run/dump978-fa/aircraft.json"
```

### API Keys

| Service | Description | How to Obtain |
|---------|-------------|---------------|
| FlightAware | AeroAPI v4 access | [FlightAware Developer Portal](https://flightaware.com/commercial/aeroapi/) |
| Flightradar24 | Commercial API token | [Flightradar24 API](https://www.flightradar24.com/premium/) |
| Google Maps | Maps JavaScript API | [Google Cloud Console](https://console.cloud.google.com/) |

API keys are optional. The application works with local data only if no API keys are configured.

## Deployment Examples

### Example 1: All-in-One on Raspberry Pi

Run everything on the RPi with the ADS-B receiver:

```yaml
local_sources:
  tracker_host: "localhost"
  dump1090: ""
  dump978: ""

server:
  host: "0.0.0.0"  # Allow network access
  port: 5000
```

Access from any device on your network at `http://<rpi-ip>:5000`

### Example 2: RPi Receiver + Ubuntu Desktop

RPi runs Dump1090, Ubuntu runs the tracker application:

```yaml
# On Ubuntu desktop
local_sources:
  tracker_host: "192.168.1.100"  # RPi IP address
  dump1090: ""
  dump978: ""

server:
  host: "127.0.0.1"  # Local access only
  port: 5000
```

### Example 3: Multiple Receivers

Combine data from multiple ADS-B receivers:

```yaml
local_sources:
  tracker_host: "localhost"
  dump1090: "http://receiver1.local:8080/data/aircraft.json"
  dump978: "http://receiver2.local:8978/data/aircraft.json"
```

## Map Legend

| Icon | Color | Description |
|------|-------|-------------|
| House | Green | Observer location |
| Circle | Red | Range boundary |
| Aircraft | Green | Local ADS-B data (Dump1090/978) |
| Aircraft | Purple | Merged (local + remote) |
| Aircraft | Blue | FlightAware only |
| Aircraft | Gold | Flightradar24 only |

## Project Structure

```
UnifiedFlightTracker/
├── app.py                 # Flask application entry point
├── config.yaml            # Configuration file (git-ignored)
├── requirements.txt       # Python dependencies
├── templates/
│   └── index.html         # Web dashboard (HTML/CSS/JS)
├── tracker/
│   ├── __init__.py
│   ├── api.py             # FlightAware and FR24 API clients
│   ├── config.py          # Configuration management
│   ├── core.py            # Deconfliction and merging logic
│   ├── geo.py             # Geodesic calculations
│   └── local.py           # Local ADS-B data fetching
└── tests/
    ├── test_logic.py      # Core logic tests
    └── test_local.py      # Local data tests
```

## Troubleshooting

### No aircraft appearing from local source

1. Verify your ADS-B receiver is running:
   ```bash
   # On the Raspberry Pi
   systemctl status dump1090-fa
   ```

2. Check if the data endpoint is accessible:
   ```bash
   curl http://localhost:8080/data/aircraft.json
   ```

3. For remote connections, ensure the RPi allows network access:
   ```bash
   # From your remote machine
   curl http://<rpi-ip>:8080/data/aircraft.json
   ```

### Connection refused to remote tracker

1. Verify the RPi IP address is correct
2. Check firewall settings on the RPi:
   ```bash
   sudo ufw status
   ```
3. Ensure lighttpd or the dump1090 web server is running

### API data not appearing

1. Verify API keys are correctly entered in `config.yaml`
2. Check the application logs for API errors
3. FlightAware and FR24 require valid subscriptions

## Testing

Run the test suite:

```bash
python3 -m pytest tests/ -v
```

Or with unittest:

```bash
python3 -m unittest discover tests
```

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Commit changes: `git commit -m "Add your feature"`
4. Push to the branch: `git push origin feature/your-feature`
5. Open a pull request

## License

See LICENSE file for details.

Code by Dr. Robert W McGwier and web ui with Claude

