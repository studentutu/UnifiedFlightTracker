"""Local ADS-B data fetching from dump1090 and dump978 sources."""

import json
import logging
import time
import os
from typing import Any, Optional

import requests

from .config import load_config

logger = logging.getLogger(__name__)

# Maximum age in seconds for aircraft to be considered "active"
MAX_AIRCRAFT_AGE_SECONDS = 60

DEFAULT_PATHS: dict[str, str] = {
    "dump1090": "/run/dump1090-fa/aircraft.json",
    "dump978": "/run/dump978-fa/aircraft.json"
}

DEFAULT_URLS: dict[str, str] = {
    "dump1090": "http://localhost:8080/data/aircraft.json",
    "dump978": "http://localhost:8978/data/aircraft.json"
}


def fetch_json_from_path_or_url(path_or_url: str) -> Optional[dict[str, Any]]:
    """
    Reads JSON from a local file path or a URL.

    Args:
        path_or_url: Either a filesystem path or HTTP(S) URL

    Returns:
        Parsed JSON dict or None if fetch failed
    """
    try:
        if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
            response = requests.get(path_or_url, timeout=2)
            response.raise_for_status()
            logger.debug(f"Fetched local data from URL: {path_or_url}")
            return response.json()
        else:
            if os.path.exists(path_or_url):
                with open(path_or_url, 'r') as f:
                    data = json.load(f)
                    logger.debug(f"Fetched local data from file: {path_or_url}")
                    return data
            else:
                logger.debug(f"Local file not found: {path_or_url}")
    except requests.RequestException as e:
        logger.warning(f"HTTP error fetching {path_or_url}: {e}")
    except json.JSONDecodeError as e:
        logger.warning(f"Invalid JSON from {path_or_url}: {e}")
    except OSError as e:
        logger.warning(f"File read error for {path_or_url}: {e}")
    except Exception as e:
        logger.warning(f"Unexpected error reading {path_or_url}: {e}")
    return None


def normalize_local_flight(f: dict[str, Any], source_name: str) -> Optional[dict[str, Any]]:
    """
    Normalizes a dump1090/978 aircraft object to the internal format.

    Args:
        f: Raw aircraft dict from dump1090/978
        source_name: Label for the data source (e.g., "Local (1090)")

    Returns:
        Normalized flight dict or None if required fields missing
    """
    # Hex is mandatory
    hex_id = f.get('hex')
    if not hex_id:
        return None

    # Lat/Lon are mandatory for the map
    lat = f.get('lat')
    lon = f.get('lon')
    if lat is None or lon is None:
        return None

    # Handle 'flight' (callsign) - typically has trailing spaces in dump1090
    callsign = f.get('flight', '').strip() or hex_id

    return {
        "source": source_name,
        "hex_id": hex_id.lower(),
        "callsign": callsign,
        "lat": lat,
        "lon": lon,
        "heading": f.get('track', 0),
        "altitude": f.get('alt_baro', f.get('alt_geom', 0)),
        "speed": f.get('gs', 0),
        "type": f.get('category', 'Unknown'),
        "timestamp": 0  # Placeholder, updated by caller
    }


def _fetch_source(
    sources: list[str],
    source_label: str
) -> tuple[Optional[dict[str, Any]], Optional[str]]:
    """
    Try fetching from a list of sources, returning first successful result.

    Returns:
        Tuple of (data dict or None, error message or None)
    """
    last_error = None
    for src in sources:
        data = fetch_json_from_path_or_url(src)
        if data is not None:
            return data, None
        last_error = src

    # All sources failed
    if last_error:
        return None, f"{source_label}: No data from configured sources"
    return None, None


def fetch_local_data() -> tuple[list[dict[str, Any]], list[str]]:
    """
    Fetches data from dump1090 and dump978 sources.

    Tries configured path first, then falls back to defaults (path, then URL).

    Returns:
        Tuple of (list of normalized flights, list of error messages)
    """
    config = load_config()
    local_conf = config.get('local_sources', {})

    # Determine sources for 1090
    sources_1090: list[str] = []
    if local_conf.get('dump1090'):
        sources_1090.append(local_conf['dump1090'])
    else:
        sources_1090 = [DEFAULT_PATHS['dump1090'], DEFAULT_URLS['dump1090']]

    # Determine sources for 978
    sources_978: list[str] = []
    if local_conf.get('dump978'):
        sources_978.append(local_conf['dump978'])
    else:
        sources_978 = [DEFAULT_PATHS['dump978'], DEFAULT_URLS['dump978']]

    flights: list[dict[str, Any]] = []
    errors: list[str] = []

    # Fetch 1090
    data_1090, err_1090 = _fetch_source(sources_1090, "Dump1090")
    if data_1090:
        now_ts = data_1090.get('now', time.time())
        for f in data_1090.get('aircraft', []):
            seen = f.get('seen', 999)
            if seen > MAX_AIRCRAFT_AGE_SECONDS:
                continue
            norm = normalize_local_flight(f, "Local (1090)")
            if norm:
                norm['timestamp'] = int(now_ts - seen)
                flights.append(norm)
    elif err_1090 and local_conf.get('dump1090'):
        # Only report error if user explicitly configured a source
        errors.append(err_1090)

    # Fetch 978
    data_978, err_978 = _fetch_source(sources_978, "Dump978")
    if data_978:
        now_ts = data_978.get('now', time.time())
        for f in data_978.get('aircraft', []):
            seen = f.get('seen', 999)
            if seen > MAX_AIRCRAFT_AGE_SECONDS:
                continue
            norm = normalize_local_flight(f, "Local (978)")
            if norm:
                norm['timestamp'] = int(now_ts - seen)
                flights.append(norm)
    elif err_978 and local_conf.get('dump978'):
        # Only report error if user explicitly configured a source
        errors.append(err_978)

    return flights, errors
