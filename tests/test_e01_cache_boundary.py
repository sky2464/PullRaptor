"""Real-filesystem regressions for private cache admission and atomic writes."""
from dataclasses import replace
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pullraptor.cache import cache_key, load_facts, store_facts
from pullraptor.models import ContentFacts, Limits, RecordLimits
from pullraptor.parser_worker import EXTRACTOR_DIGEST


class TestE01CacheBoundary(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.cache = self.root / 'cache'
        self.cache.mkdir(mode=0o700)
        self.facts = ContentFacts('a'*64, '3.12.15', '1', EXTRACTOR_DIGEST, (), (), (), (), ())
        self.key = cache_key(self.facts.blob_digest, self.facts.runtime_version,
                             self.facts.schema_version, self.facts.extractor_digest)
        self.limits = Limits()

    def tearDown(self):
        self.tmp.cleanup()

    def write_entry(self, key=None, facts=None):
        from dataclasses import asdict
        entry = self.cache / f'{key or self.key}.json'
        entry.write_text(json.dumps(asdict(facts or self.facts)))
        entry.chmod(0o600)
        return entry

    def test_shared_cache_directory_receives_no_write(self):
        self.cache.chmod(0o755)
        store_facts(self.cache, self.key, self.facts, self.limits)
        self.assertEqual(list(self.cache.iterdir()), [])

    def test_shared_entry_and_hardlink_are_misses(self):
        entry = self.write_entry()
        entry.chmod(0o644)
        self.assertIsNone(load_facts(self.cache, self.key, self.limits))
        entry.chmod(0o600)
        os.link(entry, self.root/'foreign-link')
        self.assertIsNone(load_facts(self.cache, self.key, self.limits))

    def test_valid_facts_under_wrong_key_are_misses(self):
        other = 'f'*64
        self.write_entry(key=other)
        self.assertIsNone(load_facts(self.cache, other, self.limits))
        store_facts(self.cache, other, self.facts, self.limits)
        self.assertIsNone(load_facts(self.cache, other, self.limits))

    def test_ancestor_symlink_refuses_read_and_write(self):
        self.write_entry()
        alias = self.root/'alias'
        alias.symlink_to(self.root, target_is_directory=True)
        self.assertIsNone(load_facts(alias/'cache', self.key, self.limits))
        extra = replace(self.facts, blob_digest='b'*64)
        key = cache_key(extra.blob_digest, extra.runtime_version, extra.schema_version, extra.extractor_digest)
        store_facts(alias/'cache', key, extra, self.limits)
        self.assertFalse((self.cache/f'{key}.json').exists())

    def test_predictable_temp_symlink_never_changes_external_bytes(self):
        victim = self.root/'victim'
        victim.write_bytes(b'unchanged')
        trap = self.cache/f'.tmp.{self.key}.{os.getpid()}'
        trap.symlink_to(victim)
        store_facts(self.cache, self.key, self.facts, self.limits)
        self.assertEqual(victim.read_bytes(), b'unchanged')

    def test_overcap_entry_is_rejected_before_unbounded_read(self):
        entry = self.cache/f'{self.key}.json'
        entry.write_bytes(b'x'*1025)
        entry.chmod(0o600)
        limits = replace(self.limits, record_limits=RecordLimits(max_payload_bytes=1024))
        with patch.object(Path, 'read_bytes', wraps=entry.read_bytes) as reads:
            self.assertIsNone(load_facts(self.cache, self.key, limits))
            self.assertEqual(reads.call_count, 0)

    def test_unsafe_keys_do_not_escape_cache(self):
        for key in ('../escape', '/absolute', 'a'*63, 'A'*64, ''):
            store_facts(self.cache, key, self.facts, self.limits)
            self.assertIsNone(load_facts(self.cache, key, self.limits))
        self.assertEqual(list(self.cache.iterdir()), [])

    def test_cache_key_components_have_no_delimiter_alias(self):
        self.assertNotEqual(cache_key('a:b', 'c', 'd', 'e'), cache_key('a', 'b:c', 'd', 'e'))

    def test_store_cannot_grow_beyond_entry_scan_cap(self):
        store_facts(self.cache, self.key, self.facts, self.limits)
        other = replace(self.facts, blob_digest='b'*64)
        other_key = cache_key(other.blob_digest, other.runtime_version, other.schema_version, other.extractor_digest)
        store_facts(self.cache, other_key, other, replace(self.limits, max_tracked_entries=1))
        self.assertLessEqual(len(list(self.cache.iterdir())), 1)

    def test_private_creation_and_atomic_replacement(self):
        target = self.root/'new-parent'/'new-cache'
        store_facts(target, self.key, self.facts, self.limits)
        entry = target/f'{self.key}.json'
        self.assertEqual(target.stat().st_mode & 0o777, 0o700)
        self.assertEqual(entry.stat().st_mode & 0o777, 0o600)
        first_inode = entry.stat().st_ino
        store_facts(target, self.key, self.facts, self.limits)
        self.assertNotEqual(first_inode, entry.stat().st_ino)
        self.assertEqual(load_facts(target, self.key, self.limits), self.facts)
        self.assertEqual(list(target.glob('.tmp.*')), [])

    def test_random_temp_collision_is_not_overwritten(self):
        trap = self.cache/'.tmp.fixed'
        trap.write_bytes(b'not-owned-by-this-write')
        trap.chmod(0o600)
        with patch('pullraptor.cache.secrets.token_hex', return_value='fixed'):
            store_facts(self.cache, self.key, self.facts, self.limits)
        self.assertEqual(trap.read_bytes(), b'not-owned-by-this-write')
        self.assertFalse((self.cache/f'{self.key}.json').exists())

    def test_foreign_entry_is_not_read_or_replaced(self):
        entry = self.write_entry()
        uid = os.getuid()
        original = os.fstat
        def foreign_entry(fd):
            info = original(fd)
            if info.st_ino == entry.stat().st_ino:
                values = list(info)
                values[4] = uid+1
                return os.stat_result(values)
            return info
        with patch('pullraptor.cache.os.fstat', side_effect=foreign_entry):
            self.assertIsNone(load_facts(self.cache, self.key, self.limits))
        # A real cross-user chown requires privilege; ownership predicate is
        # exercised with the opened real entry's metadata and a foreign UID.

    def test_foreign_cache_directory_refuses_read_and_write(self):
        entry = self.write_entry()
        before = entry.read_bytes()
        inode = self.cache.stat().st_ino
        original = os.fstat
        def foreign_directory(fd):
            info = original(fd)
            if info.st_ino == inode:
                values = list(info)
                values[4] = os.getuid()+1
                return os.stat_result(values)
            return info
        with patch('pullraptor.cache.os.fstat', side_effect=foreign_directory):
            self.assertIsNone(load_facts(self.cache, self.key, self.limits))
            store_facts(self.cache, self.key, self.facts, self.limits)
        self.assertEqual(entry.read_bytes(), before)
        self.assertEqual(len(list(self.cache.iterdir())), 1)

    def test_foreign_entry_prevents_cache_write(self):
        entry = self.write_entry()
        before = entry.read_bytes()
        inode = entry.stat().st_ino
        original = os.stat
        def foreign_file(*args, **kwargs):
            info = original(*args, **kwargs)
            if info.st_ino == inode:
                values = list(info)
                values[4] = os.getuid()+1
                return os.stat_result(values)
            return info
        with patch('pullraptor.cache.os.stat', side_effect=foreign_file):
            store_facts(self.cache, self.key, self.facts, self.limits)
        self.assertEqual(entry.read_bytes(), before)

    def test_symlink_and_hardlink_targets_are_not_replaced(self):
        victim = self.root/'private-victim'
        victim.write_bytes(b'unchanged')
        victim.chmod(0o600)
        target = self.cache/f'{self.key}.json'
        target.symlink_to(victim)
        self.assertIsNone(load_facts(self.cache, self.key, self.limits))
        store_facts(self.cache, self.key, self.facts, self.limits)
        self.assertTrue(target.is_symlink())
        self.assertEqual(victim.read_bytes(), b'unchanged')
        target.unlink()
        os.link(victim, target)
        self.assertIsNone(load_facts(self.cache, self.key, self.limits))
        store_facts(self.cache, self.key, self.facts, self.limits)
        self.assertEqual(target.stat().st_ino, victim.stat().st_ino)
        self.assertEqual(victim.read_bytes(), b'unchanged')

    def test_growing_entry_read_is_bounded_and_becomes_a_miss(self):
        entry = self.write_entry()
        original = os.read
        total = 0
        first = True
        cap = entry.stat().st_size+8
        def growing(fd, count):
            nonlocal total, first
            if first:
                with entry.open('ab') as handle:
                    handle.write(b'x'*(cap*3))
                first = False
            data = original(fd, count)
            total += len(data)
            return data
        limits = replace(self.limits, record_limits=RecordLimits(max_payload_bytes=cap))
        with patch('pullraptor.cache.os.read', side_effect=growing):
            self.assertIsNone(load_facts(self.cache, self.key, limits))
        self.assertLessEqual(total, cap+1)

    def test_byte_cap_evicts_private_entries_and_preserves_unknown_files(self):
        entry = self.write_entry()
        size = entry.stat().st_size
        other = replace(self.facts, blob_digest='b'*64)
        other_key = cache_key(other.blob_digest, other.runtime_version, other.schema_version, other.extractor_digest)
        store_facts(self.cache, other_key, other, replace(self.limits, max_cache_bytes=size))
        self.assertFalse(entry.exists())
        self.assertIsNotNone(load_facts(self.cache, other_key, self.limits))
        unknown = self.cache/'retain-me'
        unknown.write_bytes(b'private')
        unknown.chmod(0o600)
        before = unknown.read_bytes()
        store_facts(self.cache, self.key, self.facts, replace(self.limits, max_cache_bytes=1))
        self.assertEqual(unknown.read_bytes(), before)

    def test_scanning_over_cap_refuses_new_write(self):
        self.write_entry()
        for index in range(3):
            path = self.cache/f'unknown-{index}'
            path.write_bytes(b'x')
            path.chmod(0o600)
        other = replace(self.facts, blob_digest='b'*64)
        key = cache_key(other.blob_digest, other.runtime_version, other.schema_version, other.extractor_digest)
        before = sorted(item.name for item in self.cache.iterdir())
        store_facts(self.cache, key, other, replace(self.limits, max_tracked_entries=2))
        self.assertEqual(sorted(item.name for item in self.cache.iterdir()), before)


if __name__ == '__main__':
    unittest.main()
