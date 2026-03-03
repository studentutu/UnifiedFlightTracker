"""Core deconfliction algorithm for merging flight data from multiple sources."""

from typing import Any, Optional

from .geo import haversine_distance

# Maximum distance in nautical miles for spatial merge
SPATIAL_THRESHOLD_NM = 6.0

# Keys for cached normalized values
_NORM_HEX_KEY = '_norm_hex'
_NORM_CS_KEY = '_norm_cs'


def _normalize_flights(flights: list[dict[str, Any]]) -> None:
    """Pre-normalize hex_id and callsign for all flights to avoid repeated string operations."""
    for f in flights:
        if _NORM_HEX_KEY not in f:
            f[_NORM_HEX_KEY] = str(f.get('hex_id', '')).strip().lower()
        if _NORM_CS_KEY not in f:
            cs = f.get('callsign', '')
            f[_NORM_CS_KEY] = cs.strip().upper() if cs else ''


def deconflict_data(
    fa_data: list[dict[str, Any]],
    fr24_data: list[dict[str, Any]],
    local_data: Optional[list[dict[str, Any]]] = None
) -> list[dict[str, Any]]:
    """
    Merge flight data from multiple sources with intelligent deduplication.

    Priority order:
    1. Local ADS-B data (highest priority - most accurate position)
    2. ICAO hex code match
    3. Callsign match
    4. Spatial proximity (within threshold)

    Args:
        fa_data: List of normalized flights from FlightAware
        fr24_data: List of normalized flights from Flightradar24
        local_data: List of normalized flights from local ADS-B receivers

    Returns:
        List of deduplicated, merged flights sorted by hex_id
    """
    if local_data is None:
        local_data = []

    # Pre-normalize all flights once at the start
    _normalize_flights(local_data)
    _normalize_flights(fa_data)
    _normalize_flights(fr24_data)

    merged_results: dict[str, dict[str, Any]] = {}  # hex_id -> flight dict
    callsign_index: dict[str, str] = {}  # callsign -> hex_id (for callsign lookups)

    def clean_id(f: dict[str, Any]) -> str:
        """Get pre-normalized hex_id."""
        return f.get(_NORM_HEX_KEY, '')

    def clean_callsign(f: dict[str, Any]) -> str:
        """Get pre-normalized callsign."""
        return f.get(_NORM_CS_KEY, '')

    def update_position(existing: dict[str, Any], newer: dict[str, Any]) -> None:
        """Update existing flight with newer position data if timestamp is fresher."""
        ts_exist = existing.get('timestamp', 0)
        ts_new = newer.get('timestamp', 0)

        if ts_new > ts_exist:
            existing['lat'] = newer['lat']
            existing['lon'] = newer['lon']
            existing['heading'] = newer['heading']
            existing['altitude'] = newer['altitude']
            existing['speed'] = newer['speed']
            existing['timestamp'] = ts_new

    def update_source_label(existing: dict[str, Any], source_label: str) -> None:
        """Update the source label to reflect merged data."""
        if "Local" in existing['source']:
            if source_label not in existing['source']:
                existing['source'] = f"{existing['source']} + {source_label}"
        else:
            existing['source'] = "Merged"

    # 1. Start with Local Data (Highest Priority)
    for f in local_data:
        f_id = clean_id(f)
        merged_results[f_id] = f
        cs = clean_callsign(f)
        if cs:
            callsign_index[cs] = f_id

    def try_merge(f_new: dict[str, Any], source_label: str) -> bool:
        """
        Attempt to merge a flight using hex_id or callsign match.

        Returns:
            True if merged, False if no match found
        """
        f_id = clean_id(f_new)
        cs = clean_callsign(f_new)

        # Try exact hex_id match
        if f_id in merged_results:
            existing = merged_results[f_id]
            update_position(existing, f_new)
            update_source_label(existing, source_label)
            return True

        # Try callsign match (important for FlightAware which lacks ICAO hex)
        if cs and cs in callsign_index:
            existing_id = callsign_index[cs]
            existing = merged_results[existing_id]
            update_position(existing, f_new)
            update_source_label(existing, source_label)
            return True

        return False

    def try_spatial_merge(candidate: dict[str, Any], source_label: str) -> bool:
        """
        Attempt to merge by spatial proximity within threshold.

        Returns:
            True if merged, False if no nearby match found
        """
        best_match: Optional[dict[str, Any]] = None
        min_dist = float('inf')

        c_lat, c_lon = candidate.get('lat'), candidate.get('lon')
        if c_lat is None or c_lon is None:
            return False

        for m in merged_results.values():
            m_lat, m_lon = m.get('lat'), m.get('lon')
            if m_lat is None or m_lon is None:
                continue

            dist = haversine_distance(m_lat, m_lon, c_lat, c_lon)
            if dist < min_dist and dist <= SPATIAL_THRESHOLD_NM:
                min_dist = dist
                best_match = m

        if best_match:
            update_position(best_match, candidate)
            update_source_label(best_match, source_label)
            return True

        return False

    # 2. Process FlightAware - try hex/callsign match first
    unmerged_fa: list[dict[str, Any]] = []
    for f in fa_data:
        if not try_merge(f, "FA"):
            unmerged_fa.append(f)

    # 3. Process FR24 - try hex/callsign match first
    unmerged_fr24: list[dict[str, Any]] = []
    for f in fr24_data:
        if not try_merge(f, "FR24"):
            unmerged_fr24.append(f)

    # 4. Spatial merge for remaining FA flights
    final_fa: list[dict[str, Any]] = []
    for f in unmerged_fa:
        if not try_spatial_merge(f, "FA"):
            final_fa.append(f)

    # Add remaining FA to results
    for f in final_fa:
        f_id = clean_id(f)
        merged_results[f_id] = f
        cs = clean_callsign(f)
        if cs:
            callsign_index[cs] = f_id

    # 5. Spatial merge for remaining FR24 flights
    final_fr24: list[dict[str, Any]] = []
    for f in unmerged_fr24:
        if not try_spatial_merge(f, "FR24"):
            final_fr24.append(f)

    # Add remaining FR24 to results
    for f in final_fr24:
        f_id = clean_id(f)
        merged_results[f_id] = f

    return sorted(merged_results.values(), key=lambda x: x.get('hex_id', ''))
