"""Geographic calculations for flight tracking."""

import math

# Earth radius in nautical miles
EARTH_RADIUS_NM = 3440.065

# Earth radius in meters
EARTH_RADIUS_M = 6371000.0

# Maximum latitude to avoid division by zero at poles
MAX_SAFE_LATITUDE = 89.9


def get_bounding_box(
    lat: float,
    lon: float,
    radius_nm: float
) -> tuple[float, float, float, float]:
    """
    Calculate a bounding box around a point for API queries.

    Args:
        lat: Center latitude in degrees
        lon: Center longitude in degrees
        radius_nm: Radius in nautical miles

    Returns:
        Tuple of (min_lat, max_lat, min_lon, max_lon)
    """
    # Clamp latitude to avoid division by zero near poles
    safe_lat = max(-MAX_SAFE_LATITUDE, min(MAX_SAFE_LATITUDE, lat))

    lat_delta = math.degrees(radius_nm / EARTH_RADIUS_NM)
    # Longitude degrees per NM varies with latitude
    cos_lat = math.cos(math.radians(safe_lat))
    lon_delta = math.degrees(radius_nm / EARTH_RADIUS_NM / cos_lat)

    # Clamp longitude delta to prevent extreme values at high latitudes
    # Max reasonable delta is 180 degrees (half the globe)
    lon_delta = min(lon_delta, 180.0)

    min_lat = max(-90.0, lat - lat_delta)
    max_lat = min(90.0, lat + lat_delta)
    min_lon = max(-180.0, lon - lon_delta)
    max_lon = min(180.0, lon + lon_delta)

    return round(min_lat, 4), round(max_lat, 4), round(min_lon, 4), round(max_lon, 4)


def haversine_distance(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float
) -> float:
    """
    Calculate the great-circle distance between two points using the Haversine formula.

    Args:
        lat1, lon1: First point coordinates in degrees
        lat2, lon2: Second point coordinates in degrees

    Returns:
        Distance in nautical miles
    """
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    # Clamp to [0, 1] to prevent math domain error from floating-point precision
    a = max(0.0, min(1.0, a))
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return EARTH_RADIUS_NM * c


def calculate_az_el(
    obs_lat: float,
    obs_lon: float,
    obs_alt_m: float,
    target_lat: float,
    target_lon: float,
    target_alt_m: float
) -> tuple[float, float]:
    """
    Calculate Azimuth and Elevation of a target relative to an observer.

    Uses a spherical Earth model for accurate results at aviation distances.

    Args:
        obs_lat: Observer latitude in degrees
        obs_lon: Observer longitude in degrees
        obs_alt_m: Observer altitude in meters above sea level
        target_lat: Target latitude in degrees
        target_lon: Target longitude in degrees
        target_alt_m: Target altitude in meters above sea level

    Returns:
        Tuple of (azimuth_degrees, elevation_degrees)
        - Azimuth: 0-360 degrees clockwise from North
        - Elevation: -90 to +90 degrees from horizon
    """
    lat1_rad = math.radians(obs_lat)
    lon1_rad = math.radians(obs_lon)
    lat2_rad = math.radians(target_lat)
    lon2_rad = math.radians(target_lon)

    d_lon = lon2_rad - lon1_rad

    # Azimuth Calculation (initial bearing)
    y = math.sin(d_lon) * math.cos(lat2_rad)
    x = (math.cos(lat1_rad) * math.sin(lat2_rad) -
         math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(d_lon))
    azimuth_rad = math.atan2(y, x)
    azimuth_deg = (math.degrees(azimuth_rad) + 360) % 360

    # Elevation Calculation using spherical Earth model

    # Central angle between the two points
    sin_dlat_2 = math.sin((lat2_rad - lat1_rad) / 2) ** 2
    sin_dlon_2 = math.sin(d_lon / 2) ** 2
    a = sin_dlat_2 + math.cos(lat1_rad) * math.cos(lat2_rad) * sin_dlon_2
    # Clamp to [0, 1] to prevent math domain error from floating-point precision
    a = max(0.0, min(1.0, a))
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    # Distances from Earth center
    r_obs = EARTH_RADIUS_M + obs_alt_m
    r_target = EARTH_RADIUS_M + target_alt_m

    # Slant Range via Law of Cosines
    s_sq = r_obs ** 2 + r_target ** 2 - 2 * r_obs * r_target * math.cos(c)

    # Handle coincident or very close points
    if s_sq <= 0.0001:
        if r_target > r_obs:
            return round(azimuth_deg, 1), 90.0  # Directly above
        elif r_target < r_obs:
            return round(azimuth_deg, 1), -90.0  # Directly below
        else:
            return 0.0, 0.0  # Same point

    s = math.sqrt(s_sq)

    # Zenith angle via Law of Cosines
    # cos(zenith) relates the triangle formed by Earth center, observer, target
    cos_phi = (r_target ** 2 - r_obs ** 2 - s_sq) / (2 * r_obs * s)

    # Clamp to valid domain to avoid floating point errors
    cos_phi = max(-1.0, min(1.0, cos_phi))

    phi = math.acos(cos_phi)
    elevation_deg = 90.0 - math.degrees(phi)

    return round(azimuth_deg, 1), round(elevation_deg, 1)
