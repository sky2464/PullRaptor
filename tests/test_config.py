"""Tests for PullRaptor declarative configuration and policy loading."""

import unittest

from pullraptor.config import load_config, matches_path
from pullraptor.models import Config


class TestConfig(unittest.TestCase):
    def test_defaults_exact(self) -> None:
        cfg = load_config(None)
        self.assertEqual(cfg.profile, "structural")
        self.assertEqual(cfg.max_tracked_entries, 10_000)
        self.assertEqual(cfg.max_blob_bytes, 2_097_152)
        self.assertEqual(cfg.max_total_bytes, 134_217_728)
        self.assertEqual(cfg.parse_timeout_seconds, 2.0)
        self.assertEqual(cfg.review_timeout_seconds, 60.0)
        self.assertEqual(cfg.failure_reserve_seconds, 2.0)
        self.assertEqual(cfg.max_cache_bytes, 268_435_456)
        self.assertTrue(cfg.use_cache)
        self.assertEqual(cfg.path_include, ())
        self.assertEqual(cfg.path_exclude, ())
        self.assertIn(".py", cfg.source_suffixes)
        self.assertIn(".ts", cfg.source_suffixes)
        self.assertIn(".go", cfg.source_suffixes)

    def test_unknown_key_error(self) -> None:
        toml_bytes = b"""
        unknown_key = 123
        """
        with self.assertRaises(ValueError) as ctx:
            load_config(toml_bytes)
        self.assertIn("unknown", str(ctx.exception).lower())

        with self.assertRaises(ValueError) as ctx2:
            load_config(None, overrides={"bad_override": True})
        self.assertIn("unknown", str(ctx2.exception).lower())

    def test_glob_semantics(self) -> None:
        # normalizes path separators to /
        self.assertTrue(matches_path("src\\app\\main.py", ("src/app/*.py",)))
        self.assertTrue(matches_path("src/app/main.py", ("src/app/*.py",)))

        # * matches within a segment or whatever fnmatchcase does
        self.assertTrue(matches_path("src/foo.py", ("*.py", "src/*.py")))
        self.assertFalse(matches_path("src/foo.txt", ("src/*.py",)))

        # Case-sensitive matching
        self.assertFalse(matches_path("src/Foo.py", ("src/foo.py",)))

        # ** has no special recursive meaning beyond fnmatchcase
        # Under fnmatchcase, '*' matches anything including slashes, but '**' is not a separate globstar
        self.assertTrue(matches_path("src/app/util/foo.py", ("src/*",)))

    def test_ci_override_cannot_weaken_required_scope(self) -> None:
        base_toml = b"""
        profile = "structural"
        max_blob_bytes = 2097152
        review_timeout_seconds = 60.0
        """
        # Switching profile to diff in CI weakens required scope
        with self.assertRaises(ValueError) as ctx:
            load_config(base_toml, overrides={"profile": "diff"}, ci=True)
        self.assertIn("weaken", str(ctx.exception).lower())

        # Lowering limits in CI weakens analysis
        with self.assertRaises(ValueError) as ctx:
            load_config(base_toml, overrides={"max_blob_bytes": 1024}, ci=True)
        self.assertIn("weaken", str(ctx.exception).lower())

        # Adding exclusions in CI weakens scope
        with self.assertRaises(ValueError) as ctx:
            load_config(base_toml, overrides={"path_exclude": ["src/*"]}, ci=True)
        self.assertIn("weaken", str(ctx.exception).lower())

        # Permitted in CI: strengthening limits or keeping them the same
        cfg = load_config(base_toml, overrides={"max_blob_bytes": 4194304}, ci=True)
        self.assertEqual(cfg.max_blob_bytes, 4194304)

        # In non-CI, overrides can do whatever operator requests
        cfg_non_ci = load_config(base_toml, overrides={"profile": "diff"}, ci=False)
        self.assertEqual(cfg_non_ci.profile, "diff")

    def test_minimum_finalization_capacity(self) -> None:
        # duration below 3 seconds is a configuration error
        with self.assertRaises(ValueError) as ctx:
            load_config(None, overrides={"review_timeout_seconds": 2.5})
        self.assertIn("3", str(ctx.exception))

        # failure reserve >= duration is a configuration error
        with self.assertRaises(ValueError) as ctx:
            load_config(None, overrides={"review_timeout_seconds": 4.0, "failure_reserve_seconds": 4.5})
        self.assertIn("reserve", str(ctx.exception).lower())


if __name__ == "__main__":
    unittest.main()
