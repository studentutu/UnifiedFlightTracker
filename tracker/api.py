"""Remote API integrations for FlightAware and Flightradar24."""

import logging
import time
from datetime import datetime, timezone
from typing import Any

import requests

from .geo import get_bounding_box
from .config import load_config

logger = logging.getLogger(__name__)

# API request timeout in seconds
API_TIMEOUT_SECONDS = 5


def parse_fa_time(iso_str: str) -> int:
    """
    Parse FlightAware ISO timestamp to Unix timestamp.

    Args:
        iso_str: ISO 8601 timestamp string (e.g., "2023-01-01T12:00:00.123Z")

    Returns:
        Unix timestamp as integer
    """
    try:
        # Strip fractional seconds if present
        if '.' in iso_str:
            iso_str = iso_str.split('.')[0] + 'Z'

        dt = datetime.strptime(iso_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        return int(dt.timestamp())
    except (ValueError, AttributeError) as e:
        logger.warning(f"Failed to parse FlightAware time {iso_str}: {e}")
        return int(time.time())


def _is_api_key_valid(key: Any) -> bool:
    """Check if an API key is configured and not a placeholder."""
    if not key:
        return False
    key_str = str(key).strip()
    return key_str != "" and "YOUR_" not in key_str


def fetch_flightaware(
    lat: float,
    lon: float,
    radius_nm: float
) -> tuple[list[dict[str, Any]], list[str]]:
    """
    Fetch flight data from FlightAware AeroAPI v4.

    Args:
        lat: Center latitude in degrees
        lon: Center longitude in degrees
        radius_nm: Search radius in nautical miles

    Returns:
        Tuple of (list of normalized flights, list of error messages)
    """
    config = load_config()
    api_key = config['api_keys'].get('flightaware')

    # Silent disable if key not configured
    if not _is_api_key_valid(api_key):
        return [], []

    min_lat, max_lat, min_lon, max_lon = get_bounding_box(lat, lon, radius_nm)
    url = "https://aeroapi.flightaware.com/aeroapi/flights/search"
    query = f'-latlong "{min_lat} {min_lon} {max_lat} {max_lon}"'
    headers = {"x-apikey": api_key, "Accept": "application/json; charset=UTF-8"}
    params = {"query": query, "max_pages": 1}

    try:
        response = requests.get(url, headers=headers, params=params, timeout=API_TIMEOUT_SECONDS)
        response.raise_for_status()
        data = response.json()

        normalized_flights: list[dict[str, Any]] = []
        for f in data.get('flights', []):
            pos = f.get('last_position')
            if not pos:
                continue

            ident = f.get('ident') or 'Unknown'
            ts = parse_fa_time(pos.get('timestamp', ''))

            # FA altitude is in hundreds of feet (flight level), convert to feet
            altitude_fl = pos.get('altitude')
            altitude_ft = altitude_fl * 100 if altitude_fl else 0

            normalized_flights.append({
                "source": "FlightAware",
                # FA doesn't provide ICAO hex codes - use prefixed ident to avoid false matches
                # Deconfliction will use callsign matching or spatial proximity instead
                "hex_id": f"fa_{ident.lower()}",
                "callsign": ident,
                "lat": pos.get('latitude'),
                "lon": pos.get('longitude'),
                "heading": pos.get('heading', 0),
                "altitude": altitude_ft,
                "speed": pos.get('groundspeed', 0),
                "type": f.get('aircraft_type', 'Unknown'),
                "timestamp": ts
            })
        return normalized_flights, []

    except requests.exceptions.RequestException as e:
        logger.error(f"FlightAware API Error: {e}")
        msg = str(e)
        if hasattr(e, 'response') and e.response is not None:
            if e.response.status_code == 400:
                msg = "400 - Bad Request (Check Query Syntax)"
            else:
                msg = f"{e.response.status_code} - {e.response.reason}"
        return [], [f"FlightAware Error: {msg}"]
    except Exception as e:
        logger.error(f"Unexpected FlightAware Error: {e}")
        return [], [f"FlightAware Error: {str(e)}"]


def fetch_flightradar24(
    lat: float,
    lon: float,
    radius_nm: float
) -> tuple[list[dict[str, Any]], list[str]]:
    """
    Fetch flight data from Flightradar24 API.

    Args:
        lat: Center latitude in degrees
        lon: Center longitude in degrees
        radius_nm: Search radius in nautical miles

    Returns:
        Tuple of (list of normalized flights, list of error messages)
    """
    config = load_config()
    token = config['api_keys'].get('flightradar24')

    # Silent disable if token not configured
    if not _is_api_key_valid(token):
        return [], []

    min_lat, max_lat, min_lon, max_lon = get_bounding_box(lat, lon, radius_nm)
    bounds_str = f"{max_lat},{min_lat},{min_lon},{max_lon}"
    url = f"https://fr24api.flightradar24.com/api/live/flight-positions/full?bounds={bounds_str}"

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Accept-Version": "v1"
    }

    try:
        response = requests.get(url, headers=headers, timeout=API_TIMEOUT_SECONDS)
        response.raise_for_status()
        data = response.json()

        normalized_flights: list[dict[str, Any]] = []
        for f in data.get('data', []):
            raw_hex = f.get('hex')
            safe_hex = str(raw_hex).lower() if raw_hex else None
            safe_callsign = f.get('callsign') or 'Unknown'
            ts = f.get('updated', int(time.time()))

            normalized_flights.append({
                "source": "Flightradar24",
                "hex_id": safe_hex or safe_callsign.lower(),
                "callsign": safe_callsign,
                "lat": f.get('lat'),
                "lon": f.get('lon'),
                "heading": f.get('track', 0),
                "altitude": f.get('alt', 0),
                "speed": f.get('gs', 0),
                "type": f.get('type', 'Unknown'),
                "timestamp": ts
            })
        return normalized_flights, []

    except requests.exceptions.RequestException as e:
        logger.error(f"FR24 API Error: {e}")
        msg = str(e)
        if hasattr(e, 'response') and e.response is not None:
            msg = f"{e.response.status_code} - {e.response.text}"
        return [], [f"FR24 Error: {msg}"]
    except Exception as e:
        logger.error(f"Unexpected FR24 Error: {e}")
        return [], [f"FR24 Error: {str(e)}"]
