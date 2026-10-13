"""Declarative types and finite resource settings cannot weaken output finalization."""
import math
import unittest
from pullraptor.config import load_config


class ConfigContractTests(unittest.TestCase):
    def test_wrong_types_nonfinite_and_nonpositive_limits_rejected(self):
        cases = ({'max_blob_bytes': True}, {'max_total_bytes': -1}, {'parse_timeout_seconds': float('nan')},
                 {'review_timeout_seconds': float('inf')}, {'failure_reserve_seconds': 0},
                 {'path_include': 'app.py'}, {'path_exclude': [1]}, {'source_suffixes': [False]},
                 {'use_cache': 'yes'}, {'cache_dir': 1}, {'profile': 'invalid'},
                 {'max_tracked_entries': 2.5}, {'parse_timeout_seconds': False}, {'max_cache_bytes': 0})
        for overrides in cases:
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                load_config(None, overrides)

    def test_minimum_output_byte_item_depth_string_capacity(self):
        for key, minimum in (('max_report_bytes', 16384), ('max_report_items', 128),
                             ('max_report_depth', 8), ('max_report_string_bytes', 256)):
            with self.subTest(key=key):
                with self.assertRaises(ValueError): load_config(None, {key: minimum - 1})
                cfg = load_config(None, {key: minimum})
                self.assertEqual(getattr(cfg, key), minimum)

    def test_invalid_ci_override_is_configuration_error_not_type_crash(self):
        for overrides in ({'max_blob_bytes': 'bad'}, {'path_exclude': 12}, {'path_include': [False]}):
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                load_config(None, overrides, ci=True)
