"""Configuration management with file caching and thread safety."""

import os
import threading
from typing import Any

import yaml
import logging

logger = logging.getLogger(__name__)

CONFIG_FILE = 'config.yaml'

DEFAULT_CONFIG: dict[str, Any] = {
    "api_keys": {
        "flightaware": "YOUR_FLIGHTAWARE_API_KEY",
        "flightradar24": "YOUR_FR24_API_TOKEN",
        "google_maps": "YOUR_GOOGLE_MAPS_API_KEY"
    },
    "local_sources": {
        "dump1090": "/run/dump1090-fa/aircraft.json",
        "dump978": "/run/dump978-fa/aircraft.json"
    },
    "observer": {
        "latitude": 39.0,
        "longitude": -75.0,
        "altitude_m": 0,
        "radius_nm": 50
    },
    "server": {
        "host": "0.0.0.0",
        "port": 5000
    }
}

# Thread-safe cache for configuration
_config_lock = threading.Lock()
_cached_config: dict[str, Any] | None = None
_cached_mtime: float = 0


def load_config() -> dict[str, Any]:
    """
    Load configuration from YAML file with caching.

    Features:
    - Creates default config file if none exists
    - Caches config and only reloads when file mtime changes
    - Thread-safe for multi-threaded Flask deployments
    - Falls back to cached/default config on parse errors

    Returns:
        Configuration dictionary
    """
    global _cached_config, _cached_mtime

    with _config_lock:
        # Create default config if file doesn't exist
        if not os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'w') as f:
                    yaml.dump(DEFAULT_CONFIG, f, default_flow_style=False)
                _cached_config = DEFAULT_CONFIG.copy()
                _cached_mtime = os.path.getmtime(CONFIG_FILE)
                logger.info(f"Created default configuration file at {CONFIG_FILE}")
                return _cached_config
            except OSError as e:
                logger.error(f"Failed to create default config file: {e}")
                return DEFAULT_CONFIG.copy()

        # Check if file changed since last load
        try:
            current_mtime = os.path.getmtime(CONFIG_FILE)
            if _cached_config is not None and current_mtime == _cached_mtime:
                return _cached_config

            logger.info(f"Reloading configuration from {CONFIG_FILE}")
            with open(CONFIG_FILE, 'r') as f:
                config = yaml.safe_load(f)

            if not config:
                logger.warning(f"Configuration file {CONFIG_FILE} is empty.")
                if _cached_config is not None:
                    logger.warning("Retaining previous valid configuration.")
                    return _cached_config
                logger.warning("Using default configuration.")
                return DEFAULT_CONFIG.copy()

            # Merge with defaults to ensure all sections exist
            for section in DEFAULT_CONFIG:
                if section not in config:
                    config[section] = DEFAULT_CONFIG[section]
                elif isinstance(DEFAULT_CONFIG[section], dict):
                    # Deep merge for nested dicts
                    for key in DEFAULT_CONFIG[section]:
                        if key not in config[section]:
                            config[section][key] = DEFAULT_CONFIG[section][key]

            _cached_config = config
            _cached_mtime = current_mtime
            logger.info("Configuration loaded successfully.")
            return config

        except yaml.YAMLError as e:
            logger.error(f"Error parsing {CONFIG_FILE}: {e}")
            if _cached_config is not None:
                logger.warning("Retaining previous valid configuration due to parse error.")
                return _cached_config
            logger.warning("Reverting to default configuration due to parse error.")
            return DEFAULT_CONFIG.copy()

        except OSError as e:
            logger.error(f"Error reading config file: {e}")
            if _cached_config is not None:
                return _cached_config
            return DEFAULT_CONFIG.copy()

        except Exception as e:
            logger.error(f"Unexpected error loading config: {e}")
            if _cached_config is not None:
                return _cached_config
            return DEFAULT_CONFIG.copy()
