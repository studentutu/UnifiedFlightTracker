import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Flask, render_template, request, jsonify
from tracker.config import load_config, DEFAULT_CONFIG
from tracker.api import fetch_flightaware, fetch_flightradar24
from tracker.local import fetch_local_data
from tracker.core import deconflict_data
from tracker.geo import haversine_distance, calculate_az_el

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.route('/')
def index():
    config = load_config()
    api_key = config['api_keys'].get('google_maps', '')
    is_default = (api_key == DEFAULT_CONFIG['api_keys']['google_maps'])

    return render_template('index.html',
                          api_key=api_key,
                          is_default_key=is_default,
                          default_lat=config['observer']['latitude'],
                          default_lon=config['observer']['longitude'],
                          default_radius=config['observer']['radius_nm'])

@app.route('/api/flights')
def get_flights():
    # Load config (cached)
    config = load_config()

    try:
        lat = float(request.args.get('lat'))
        lon = float(request.args.get('lon'))
        radius = float(request.args.get('radius'))
    except (TypeError, ValueError):
        return jsonify({"flights": [], "messages": ["Invalid parameters"]}), 400

    # Fetch from all sources in parallel to minimize latency
    # (Critical for Raspberry Pi where sequential timeouts add up)
    local_data, local_errors = [], []
    fa_data, fa_errors = [], []
    fr24_data, fr24_errors = [], []

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(fetch_local_data): 'local',
            executor.submit(fetch_flightaware, lat, lon, radius): 'fa',
            executor.submit(fetch_flightradar24, lat, lon, radius): 'fr24',
        }

        for future in as_completed(futures):
            source = futures[future]
            try:
                data, errors = future.result()
                if source == 'local':
                    local_data, local_errors = data, errors
                elif source == 'fa':
                    fa_data, fa_errors = data, errors
                elif source == 'fr24':
                    fr24_data, fr24_errors = data, errors
            except Exception as e:
                logger.error(f"Error fetching {source} data: {e}")
                if source == 'local':
                    local_errors = [f"Local error: {e}"]
                elif source == 'fa':
                    fa_errors = [f"FlightAware error: {e}"]
                elif source == 'fr24':
                    fr24_errors = [f"FR24 error: {e}"]

    clean_data = deconflict_data(fa_data, fr24_data, local_data)

    obs_alt = config['observer'].get('altitude_m', 0)

    # Calculate distance and Az/El for each flight
    for f in clean_data:
        if f['lat'] is not None and f['lon'] is not None:
            f['distance_from_obs'] = haversine_distance(lat, lon, f['lat'], f['lon'])

            # Calculate Azimuth and Elevation
            # Aircraft altitude is in feet, convert to meters for calculation
            ac_alt_m = (f.get('altitude', 0) or 0) * 0.3048

            az, el = calculate_az_el(lat, lon, obs_alt, f['lat'], f['lon'], ac_alt_m)
            f['azimuth'] = az
            f['elevation'] = el
        else:
            f['distance_from_obs'] = float('inf')
            f['azimuth'] = 0
            f['elevation'] = 0

    return jsonify({"flights": clean_data, "messages": local_errors + fa_errors + fr24_errors})

if __name__ == '__main__':
    import os
    config = load_config()
    host = config['server']['host']
    port = config['server']['port']

    # Only enable debug mode if explicitly requested via environment variable
    # NEVER run debug=True in production - it enables arbitrary code execution
    debug_mode = os.environ.get('FLASK_DEBUG', '').lower() in ('1', 'true', 'yes')

    if debug_mode:
        logger.warning("Running in DEBUG mode - do not use in production!")
        app.run(host=host, port=port, debug=True)
    else:
        logger.info(f"Starting Flight Tracker on http://{host}:{port}")
        logger.info(f"For production, consider using: gunicorn -w 2 -b {host}:{port} app:app")
        app.run(host=host, port=port, debug=False, threaded=True)
