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

2. Check if the data endpoint is accessible locally:
   ```bash
   curl http://localhost:8080/data/aircraft.json
   ```

3. For remote connections, test from your remote machine:
   ```bash
   curl http://<rpi-ip>:8080/data/aircraft.json
   ```

### Connection refused to remote tracker

#### Step 1: Verify basic network connectivity

```bash
# Test if the RPi is reachable
ping <rpi-ip>

# Test if the port is open
nc -zv <rpi-ip> 8080
```

#### Step 2: Check firewall status on the Raspberry Pi

```bash
sudo ufw status
```

**If UFW is active and blocking connections:**

```bash
# Allow dump1090 web interface (port 8080)
sudo ufw allow 8080/tcp

# Allow dump978 web interface (port 8978)
sudo ufw allow 8978/tcp

# Allow the Flight Tracker web server (port 5000)
sudo ufw allow 5000/tcp

# Verify the rules were added
sudo ufw status
```

**If UFW is inactive but connections still fail, check iptables:**

```bash
# List current iptables rules
sudo iptables -L -n

# If needed, allow the ports (temporary, resets on reboot)
sudo iptables -A INPUT -p tcp --dport 8080 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 8978 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 5000 -j ACCEPT
```

#### Step 3: Verify the web server is listening on all interfaces

```bash
# Check what addresses dump1090 is listening on
sudo ss -tlnp | grep 8080
```

The output should show `0.0.0.0:8080` (all interfaces) not `127.0.0.1:8080` (localhost only).

**If lighttpd is only listening on localhost**, edit `/etc/lighttpd/lighttpd.conf`:

```bash
sudo nano /etc/lighttpd/lighttpd.conf
```

Change or add:
```
server.bind = "0.0.0.0"
```

Then restart lighttpd:
```bash
sudo systemctl restart lighttpd
```

#### Step 4: Verify dump1090-fa is serving data

```bash
# Check if dump1090-fa service is running
sudo systemctl status dump1090-fa

# Restart if needed
sudo systemctl restart dump1090-fa

# Check the service logs for errors
sudo journalctl -u dump1090-fa -n 50
```

#### Step 5: Check for IP address changes

If using DHCP, the RPi's IP may have changed. Find the current IP:

```bash
# On the Raspberry Pi
hostname -I
```

Update `tracker_host` in `config.yaml` on your remote machine to match.

### Network ports reference

| Service | Port | Protocol | Description |
|---------|------|----------|-------------|
| dump1090-fa | 8080 | TCP | Aircraft JSON data |
| dump978-fa | 8978 | TCP | UAT aircraft JSON data |
| Flight Tracker | 5000 | TCP | Web dashboard |
| dump1090 Beast | 30005 | TCP | Raw data feed (not needed for this app) |

### API data not appearing

1. Verify API keys are correctly entered in `config.yaml`
2. Check the application logs for API errors:
   ```bash
   # Run with debug output
   FLASK_DEBUG=1 python3 app.py
   ```
3. FlightAware and FR24 require valid paid subscriptions
4. Test API connectivity:
   ```bash
   # Test FlightAware API (replace with your key)
   curl -u "YOUR_API_KEY:" "https://aeroapi.flightaware.com/aeroapi/flights/search?query=-latlong+%2239.0+-75.0+39.5+-74.5%22"
   ```

### Common issues on Ubuntu 24.04

**Python command not found:**
```bash
# Use python3 explicitly
python3 app.py

# Or create an alias
alias python=python3
```

**Permission denied on port 5000:**
```bash
# Use a port above 1024, or run with sudo (not recommended)
# Edit config.yaml and change server.port to 8000 or similar
```

**Module not found errors:**
```bash
# Ensure virtual environment is activated
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

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

