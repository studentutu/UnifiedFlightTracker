import copy
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tracker import config as config_module


class TestConfigIsolation(unittest.TestCase):
    """DEFAULT_CONFIG must never alias into returned configs — callers mutate
    the returned dict freely (e.g. writing back an API key), and that must not
    corrupt the module-level defaults for later callers."""

    def setUp(self):
        # Isolate: swap CONFIG_FILE to a tempdir so we don't touch the real config.
        self._orig_cwd = os.getcwd()
        self._tmpdir = tempfile.mkdtemp()
        os.chdir(self._tmpdir)
        # Reset cache
        config_module._cached_config = None
        config_module._cached_mtime = 0
        self._default_snapshot = copy.deepcopy(config_module.DEFAULT_CONFIG)

    def tearDown(self):
        os.chdir(self._orig_cwd)
        config_module._cached_config = None
        config_module._cached_mtime = 0
        # Confirm we didn't leak mutations into DEFAULT_CONFIG.
        self.assertEqual(config_module.DEFAULT_CONFIG, self._default_snapshot)

    def test_default_config_not_mutated_when_file_missing(self):
        # Force the "file doesn't exist" path first, then mutate the returned config.
        cfg = config_module.load_config()
        cfg['api_keys']['flightaware'] = 'MUTATED'
        cfg['observer']['latitude'] = 999.0
        # DEFAULT_CONFIG must still show placeholders.
        self.assertEqual(
            config_module.DEFAULT_CONFIG['api_keys']['flightaware'],
            'YOUR_FLIGHTAWARE_API_KEY',
        )
        self.assertEqual(config_module.DEFAULT_CONFIG['observer']['latitude'], 39.0)

    def test_merge_deepcopies_defaults(self):
        # Write a partial config, then mutate the merged-in defaults section.
        with open('config.yaml', 'w') as f:
            f.write("observer:\n  latitude: 12.34\n  longitude: 56.78\n")
        # Bust the cache so we take the load-from-file path.
        config_module._cached_config = None
        config_module._cached_mtime = 0
        cfg = config_module.load_config()
        # api_keys section was absent — should be filled from defaults.
        self.assertIn('api_keys', cfg)
        cfg['api_keys']['flightaware'] = 'MUTATED_VIA_MERGE'
        self.assertEqual(
            config_module.DEFAULT_CONFIG['api_keys']['flightaware'],
            'YOUR_FLIGHTAWARE_API_KEY',
        )


if __name__ == '__main__':
    unittest.main()
