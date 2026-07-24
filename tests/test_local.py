import unittest
import json
import time
import os
import sys
from unittest.mock import patch, mock_open

# Add parent dir to path to import tracker
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tracker.local import fetch_local_data, normalize_local_flight
from tracker.core import deconflict_data

class TestLocalData(unittest.TestCase):

    def test_normalize_local_flight(self):
        f = {
            "hex": "A1B2C3",
            "lat": 40.0,
            "lon": -74.0,
            "flight": "TEST1   ", # Trailing spaces common in dump1090
            "track": 180,
            "alt_baro": 30000,
            "gs": 450,
            "category": "A0"
        }
        norm = normalize_local_flight(f, "Local")
        self.assertEqual(norm['hex_id'], 'a1b2c3')
        self.assertEqual(norm['callsign'], 'TEST1')
        self.assertEqual(norm['altitude'], 30000)

    def test_normalize_local_flight_ground_altitude(self):
        # dump1090 reports alt_baro as the literal string "ground" for surface aircraft.
        # Must not propagate the string — downstream code multiplies altitude as a number.
        f = {"hex": "AAAAAA", "lat": 40.0, "lon": -74.0, "alt_baro": "ground"}
        norm = normalize_local_flight(f, "Local")
        self.assertEqual(norm['altitude'], 0)
        # Ensure it survives arithmetic like the app.py alt→meters conversion.
        self.assertEqual(norm['altitude'] * 0.3048, 0.0)

    def test_normalize_local_flight_falls_back_to_alt_geom(self):
        f = {"hex": "BBBBBB", "lat": 40.0, "lon": -74.0, "alt_baro": None, "alt_geom": 12500}
        norm = normalize_local_flight(f, "Local")
        self.assertEqual(norm['altitude'], 12500)

    @patch('tracker.local.load_config')
    @patch('tracker.local.fetch_json_from_path_or_url')
    def test_fetch_local_data(self, mock_fetch, mock_config):
        mock_config.return_value = {
            'local_sources': {'dump1090': '/fake/path/1090', 'dump978': '/fake/path/978'}
        }

        # Mock 1090 data
        mock_fetch.side_effect = [
            {
                "now": 1700000000.0,
                "aircraft": [
                    {
                        "hex": "111111", "lat": 40.0, "lon": -70.0,
                        "flight": "LOC1", "seen": 0.5
                    }
                ]
            },
            None # No 978 data
        ]

        flights, errors = fetch_local_data()
        self.assertEqual(len(flights), 1)
        self.assertEqual(flights[0]['hex_id'], '111111')
        self.assertEqual(flights[0]['timestamp'], 1699999999) # 1700... - 0.5 rounded

    @patch('tracker.local.load_config')
    @patch('tracker.local.fetch_json_from_path_or_url')
    def test_fetch_local_data_handles_none_seen(self, mock_fetch, mock_config):
        # dump1090 may omit or null the 'seen' field. Prior code did f.get('seen', 999)
        # which returned None (not 999) when the key was present with value None, then
        # crashed on `None > 60`.
        mock_config.return_value = {
            'local_sources': {'dump1090': '/fake/path/1090', 'dump978': '/fake/path/978'}
        }
        mock_fetch.side_effect = [
            {
                "now": 1700000000.0,
                "aircraft": [
                    {"hex": "222222", "lat": 40.0, "lon": -70.0, "seen": None}
                ]
            },
            None
        ]
        # Should not raise; aircraft with unknown age is dropped as stale (seen=999).
        flights, _ = fetch_local_data()
        self.assertEqual(flights, [])

    def test_deconflict_local_priority(self):
        local_data = [{
            "source": "Local (1090)",
            "hex_id": "abc123",
            "lat": 40.0,
            "lon": -74.0,
            "timestamp": 1000,
            "altitude": 1000, "speed": 100, "heading": 100, "callsign": "LOC", "type": "X"
        }]

        fa_data = [{
            "source": "FlightAware",
            "hex_id": "ABC123", # Matches local
            "lat": 40.1, # Different position (older?)
            "lon": -74.1,
            "timestamp": 900, # Older
             "altitude": 1000, "speed": 100, "heading": 100, "callsign": "FA", "type": "X"
        }]

        # Case 1: Local is fresher
        merged = deconflict_data(fa_data, [], local_data)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]['lat'], 40.0)
        self.assertIn("Local", merged[0]['source'])
        self.assertIn("FA", merged[0]['source']) # Should show it merged

        # Case 2: Remote is fresher (e.g. latency in local decoder vs fast API? Unlikely but possible)
        fa_data[0]['timestamp'] = 1100
        fa_data[0]['lat'] = 40.2
        merged = deconflict_data(fa_data, [], local_data)
        self.assertEqual(merged[0]['lat'], 40.2) # Should update to fresher FA
        self.assertIn("Local", merged[0]['source']) # But keep tracking source label

if __name__ == '__main__':
    unittest.main()
