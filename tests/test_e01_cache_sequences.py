"""Full canonical replay across meaningful content/scope/policy/cache mutations."""
from dataclasses import replace
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
from pullraptor.kernel import review
from pullraptor.models import Diagnostic, FactResult, canonical_bytes
from tests.helpers import make_repo


class CacheSequenceTests(unittest.TestCase):
    def test_full_canonical_clean_warm_corrupt_absent_mutation_sequence(self):
        repo = make_repo({'app.py': b'import helper\ndef f(x=[]): x.append(1)\n', 'helper.py': b'x=1\n'})
        self.addCleanup(repo.cleanup)
        base = repo.commit_ids[0]
        with tempfile.TemporaryDirectory(prefix='e01-owned-cache-') as cache_root:
            cache = Path(cache_root) / 'private'
            cache.mkdir(mode=0o700)
            mutations = (
                ('witness_move', {'app.py': b'\n\nimport helper\ndef f(x=[]): x.append(1)\n'}, {}, 0),
                ('rename', {'app.py': None, 'renamed.py': b'import helper\ndef f(x=[]): x.append(1)\n'}, {}, 0),
                ('delete_dependency', {'helper.py': None}, {}, 2),
                ('add_missing_module', {'helper.py': b'x=2\n'}, {}, 0),
                ('alter_policy', {'.pullraptor.toml': b"profile='diff'\n"}, {}, 0),
                ('exceed_limit', {'renamed.py': b'# long\n' * 30}, {'max_blob_bytes': 64}, 2),
                ('recover_limit', {'renamed.py': b'import helper\ndef f(x=[]): x.append(2)\n'}, {}, 0),
            )
            for label, changes, overrides, expected in mutations:
                with self.subTest(mutation=label):
                    head = repo.commit(changes)
                    policy = {'cache_dir': str(cache), **overrides}
                    def run(use_cache):
                        value, deadline, limits = review(repo.root, base, head, policy,
                                                       exact_base=True, use_cache=use_cache)
                        self.assertEqual(value.kind, 'full')
                        self.assertEqual(value.execution['exit_code'], expected)
                        return value, canonical_bytes(value, limits=limits, deadline=deadline)
                    clean, canonical = run(False)
                    cold, cold_bytes = run(True)
                    warm, warm_bytes = run(True)
                    self.assertEqual(canonical, cold_bytes)
                    self.assertEqual(canonical, warm_bytes)
                    # Compare complete scope, diagnostics, findings and identity bytes,
                    # not finding counts or cache key equality.
                    for entry in cache.glob('*.json'): entry.write_bytes(b'corrupt owned entry')
                    corrupt, corrupt_bytes = run(True)
                    self.assertEqual(canonical, corrupt_bytes)
                    for entry in cache.glob('*.json'): entry.unlink()
                    absent, absent_bytes = run(True)
                    self.assertEqual(canonical, absent_bytes)
                    self.assertEqual(clean.receipts, warm.receipts)
                    self.assertEqual(clean.diagnostics, warm.diagnostics)

    def test_cold_worker_timeout_warm_completion_requires_full_clean_replay(self):
        repo = make_repo({'app.py': b'x=1\n'})
        self.addCleanup(repo.cleanup)
        head = repo.commit({'app.py': b'def f(x=[]): x.append(1)\n'})
        with tempfile.TemporaryDirectory(prefix='e01-owned-cache-') as cache:
            options = {'cache_dir': cache}
            warm, wd, wl = review(repo.root, repo.commit_ids[0], head, options, exact_base=True)
            self.assertEqual(warm.execution['exit_code'], 0)
            failure = FactResult(None, (Diagnostic('TIMEOUT', 'Owned worker deadline fixture',
                                 cause='deadline_exhausted', recovery='Increase declared parse allowance'),))
            with patch('pullraptor.kernel.extract_python', return_value=failure):
                cold, _, _ = review(repo.root, repo.commit_ids[0], head, options, exact_base=True, use_cache=False)
                completed, cd, cl = review(repo.root, repo.commit_ids[0], head, options, exact_base=True)
            self.assertEqual(cold.execution['exit_code'], 2)
            self.assertTrue(any(item.status == 'incomplete' for item in cold.receipts))
            self.assertTrue(any(item.code == 'TIMEOUT' for item in cold.diagnostics))
            self.assertEqual(completed.execution['exit_code'], 0)
            replay, rd, rl = review(repo.root, repo.commit_ids[0], head, options, exact_base=True, use_cache=False)
            self.assertEqual(replay.execution['exit_code'], 0)
            self.assertEqual(canonical_bytes(completed, limits=cl, deadline=cd),
                             canonical_bytes(replay, limits=rl, deadline=rd))
