"""Local ADS-B data fetching from dump1090 and dump978 sources.

Supports both local RPi5 deployments and remote access from x86_64 machines.
Platform detection automatically selects optimal data source paths.
"""

import json
import logging
import platform
import time
import os
from typing import Any, Optional

import requests

from .config import load_config

logger = logging.getLogger(__name__)

# Maximum age in seconds for aircraft to be considered "active"
MAX_AIRCRAFT_AGE_SECONDS = 60

# Default local file paths (used when running directly on RPi5)
DEFAULT_PATHS: dict[str, str] = {
    "dump1090": "/run/dump1090-fa/aircraft.json",
    "dump978": "/run/dump978-fa/aircraft.json"
}

# Default ports for dump1090/dump978 HTTP endpoints
DEFAULT_PORTS: dict[str, int] = {
    "dump1090": 8080,
    "dump978": 8978
}


def get_platform_info() -> dict[str, Any]:
    """
    Detect platform characteristics for optimal source selection.

    Returns:
        Dict with platform info:
        - arch: CPU architecture (aarch64, x86_64, armv7l, etc.)
        - is_arm: True if running on ARM (RPi5, RPi4, etc.)
        - is_x86_64: True if running on x86_64
        - is_local_tracker: True if likely running on a device with local dump1090
    """
    arch = platform.machine().lower()
    is_arm = arch in ('aarch64', 'arm64', 'armv7l', 'armv8l')
    is_x86_64 = arch in ('x86_64', 'amd64')

    # Check if local dump1090 paths exist (indicates we're on the tracker device)
    has_local_dump1090 = os.path.exists('/run/dump1090-fa') or os.path.exists('/run/readsb')
    has_local_dump978 = os.path.exists('/run/dump978-fa')

    is_local_tracker = has_local_dump1090 or has_local_dump978

    return {
        "arch": arch,
        "is_arm": is_arm,
        "is_x86_64": is_x86_64,
        "is_local_tracker": is_local_tracker
    }


def build_url(host: str, service: str) -> str:
    """
    Build HTTP URL for a dump1090/dump978 service.

    Args:
        host: Hostname or IP address (e.g., "localhost", "192.168.1.100")
        service: Service name ("dump1090" or "dump978")

    Returns:
        Full URL to the aircraft.json endpoint
    """
    port = DEFAULT_PORTS.get(service, 8080)
    return f"http://{host}:{port}/data/aircraft.json"


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
    except requests.exceptions.Timeout as e:
        logger.warning(f"HTTP timeout fetching {path_or_url}: {e}")
    except requests.exceptions.ConnectionError as e:
        logger.debug(f"Connection error fetching {path_or_url}: {e}")
    except requests.exceptions.RequestException as e:
        logger.warning(f"HTTP error fetching {path_or_url}: {e}")
    except json.JSONDecodeError as e:
        logger.warning(f"Invalid JSON from {path_or_url}: {e}")
    except OSError as e:
        logger.warning(f"File read error for {path_or_url}: {e}")
    except (TypeError, ValueError) as e:
        logger.warning(f"Data parsing error from {path_or_url}: {e}")
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

    # dump1090 reports alt_baro as the literal string "ground" when an aircraft
    # is on the surface; treat it as altitude 0 so downstream unit conversions
    # don't crash on non-numeric input.
    raw_alt = f.get('alt_baro')
    if raw_alt is None or isinstance(raw_alt, str):
        raw_alt = f.get('alt_geom')
    if raw_alt is None or isinstance(raw_alt, str):
        raw_alt = 0

    return {
        "source": source_name,
        "hex_id": hex_id.lower(),
        "callsign": callsign,
        "lat": lat,
        "lon": lon,
        "heading": f.get('track', 0),
        "altitude": raw_alt,
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


def _get_sources_for_service(
    service: str,
    local_conf: dict[str, Any],
    platform_info: dict[str, Any]
) -> list[str]:
    """
    Determine data sources for a service based on config and platform.

    Priority:
    1. Explicit config value (if set and non-empty)
    2. Platform-aware auto-detection:
       - On local tracker (RPi5): file path first, then localhost URL
       - On remote x86_64: HTTP URL using tracker_host

    Args:
        service: "dump1090" or "dump978"
        local_conf: local_sources config section
        platform_info: Result of get_platform_info()

    Returns:
        List of sources to try in order
    """
    # Check for explicit configuration
    configured = local_conf.get(service, "")
    if configured:
        return [configured]

    # Get tracker host from config (default: localhost)
    tracker_host = local_conf.get('tracker_host', 'localhost')

    sources: list[str] = []

    if platform_info['is_local_tracker']:
        # Running on the tracker device - prefer local files
        sources.append(DEFAULT_PATHS[service])
        sources.append(build_url('localhost', service))
        logger.debug(f"Platform: local tracker, using file paths first for {service}")
    elif tracker_host == 'localhost' or tracker_host == '127.0.0.1':
        # localhost configured but not on tracker device - try both
        sources.append(DEFAULT_PATHS[service])
        sources.append(build_url('localhost', service))
        logger.debug(f"Platform: localhost configured, trying file then HTTP for {service}")
    else:
        # Remote tracker host configured - use HTTP only
        sources.append(build_url(tracker_host, service))
        logger.debug(f"Platform: remote tracker at {tracker_host} for {service}")

    return sources


def fetch_local_data() -> tuple[list[dict[str, Any]], list[str]]:
    """
    Fetches data from dump1090 and dump978 sources.

    Platform-aware source selection:
    - On RPi5 (ARM with local dump1090): Uses local file paths first
    - On remote x86_64: Uses HTTP to configured tracker_host

    Configure tracker_host in config.yaml to point to remote RPi5:
        local_sources:
            tracker_host: "192.168.1.100"  # IP of your RPi5

    Returns:
        Tuple of (list of normalized flights, list of error messages)
    """
    config = load_config()
    local_conf = config.get('local_sources', {})
    platform_info = get_platform_info()

    logger.debug(f"Platform info: arch={platform_info['arch']}, "
                 f"is_local_tracker={platform_info['is_local_tracker']}")

    # Determine sources based on platform and config
    sources_1090 = _get_sources_for_service('dump1090', local_conf, platform_info)
    sources_978 = _get_sources_for_service('dump978', local_conf, platform_info)

    flights: list[dict[str, Any]] = []
    errors: list[str] = []

    # Fetch 1090
    data_1090, err_1090 = _fetch_source(sources_1090, "Dump1090")
    if data_1090:
        now_ts = data_1090.get('now')
        if now_ts is None:
            now_ts = time.time()
        for f in data_1090.get('aircraft', []):
            seen = f.get('seen')
            if seen is None:
                seen = 999
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
        now_ts = data_978.get('now')
        if now_ts is None:
            now_ts = time.time()
        for f in data_978.get('aircraft', []):
            seen = f.get('seen')
            if seen is None:
                seen = 999
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
