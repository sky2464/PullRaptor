"""Tests for PullRaptor parse cache."""

import os
from pathlib import Path
import tempfile
import time
import unittest

from pullraptor.cache import cache_key, load_facts, store_facts
from pullraptor.models import ContentFacts, Limits
from pullraptor.parser_worker import EXTRACTOR_DIGEST


class TestCache(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp(prefix="pullraptor_test_cache_")
        self.cache_dir = Path(self.temp_dir).resolve()
        self.limits = Limits()

    def tearDown(self) -> None:
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _make_sample_facts(self, digest: str = "a" * 64) -> ContentFacts:
        return ContentFacts(
            blob_digest=digest,
            runtime_version="3.12.15",
            schema_version="1",
            extractor_digest=EXTRACTOR_DIGEST,
            symbols=(),
            imports=(),
            pattern_facts=(),
            unsupported_constructs=(),
            relative_locations=(),
        )

    def test_clean_warm_corrupt_cache_identical(self) -> None:
        facts = self._make_sample_facts()
        key = cache_key(facts.blob_digest, facts.runtime_version, facts.schema_version, facts.extractor_digest)

        # Cold read -> None
        loaded = load_facts(self.cache_dir, key, self.limits)
        self.assertIsNone(loaded)

        # Store -> Warm read
        store_facts(self.cache_dir, key, facts, self.limits)
        loaded_warm = load_facts(self.cache_dir, key, self.limits)
        self.assertIsNotNone(loaded_warm)
        self.assertEqual(loaded_warm.blob_digest, facts.blob_digest)

        # Corrupt file
        cache_file = self.cache_dir / f"{key}.json"
        cache_file.write_bytes(b"CORRUPT JSON NOT VALID")
        loaded_corrupt = load_facts(self.cache_dir, key, self.limits)
        self.assertIsNone(loaded_corrupt)

    def test_runtime_schema_change_miss(self) -> None:
        facts = self._make_sample_facts()
        key1 = cache_key(facts.blob_digest, "3.12.15", "1", "ext1")
        key2 = cache_key(facts.blob_digest, "3.13.0", "1", "ext1")
        key3 = cache_key(facts.blob_digest, "3.12.15", "2", "ext1")
        key4 = cache_key(facts.blob_digest, "3.12.15", "1", "ext2")

        self.assertNotEqual(key1, key2)
        self.assertNotEqual(key1, key3)
        self.assertNotEqual(key1, key4)

    def test_cache_symlink_refused(self) -> None:
        facts = self._make_sample_facts()
        key = cache_key(facts.blob_digest, facts.runtime_version, facts.schema_version, facts.extractor_digest)
        store_facts(self.cache_dir, key, facts, self.limits)

        # Create symlink pointing to cache entry
        symlink_key = "f" * 64
        symlink_file = self.cache_dir / f"{symlink_key}.json"
        try:
            symlink_file.symlink_to(self.cache_dir / f"{key}.json")
            # Loading via symlink must be refused
            loaded = load_facts(self.cache_dir, symlink_key, self.limits)
            self.assertIsNone(loaded)
        except OSError:
            pass


if __name__ == "__main__":
    unittest.main()
