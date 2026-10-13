"""Reproduced full-E01 scope, parser and rule contract deviations."""
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from dataclasses import replace

from pullraptor.kernel import review
from pullraptor.models import BlobRef, Config, Deadline, Limits, Snapshot
from pullraptor.python_facts import bind_facts, extract_python, resolve_context
from pullraptor.rules import evaluate_rules
from tests.helpers import make_repo


class CoreRegressionTests(unittest.TestCase):
    def test_structural_other_language_partial_exit2(self):
        repo = make_repo({'app.js': b'const x = 1;\n'})
        self.addCleanup(repo.cleanup)
        head = repo.commit({'app.js': b'const x = 2;\n'})
        value, _, _ = review(repo.root, repo.commit_ids[0], head, exact_base=True, use_cache=False)
        self.assertEqual(value.execution['exit_code'], 2)
        required = [item for item in value.contract.expected_scope if item.path == 'app.js']
        self.assertTrue(required)
        self.assertTrue(any(item.status == 'incomplete' and item.cause == 'unsupported_language'
                            for item in value.receipts))
        self.assertTrue(any(item.recovery and item.cause == 'unsupported_language' for item in value.diagnostics))

    def test_constructor_defaults_and_typed_handlers_are_outside_pattern_scope(self):
        for source, rule in ((b'def f(x=set()): x.add(1)', 'PY001'),
                             (b'def f(x=list()): x.append(1)', 'PY001'),
                             (b'try: pass\nexcept BaseException: pass', 'PY002')):
            with self.subTest(source=source):
                limits = Limits()
                facts = extract_python(source, limits, Deadline(time.monotonic(), 30)).content
                self.assertIsNotNone(facts)
                blob = BlobRef('app.py', b'app.py', '100644', 'x', len(source))
                snapshot = Snapshot('head', (blob,))
                bound = bind_facts(facts, source, snapshot, 'app.py', 'head')
                resolved, _ = resolve_context((bound,), snapshot)
                findings = evaluate_rules(resolved, snapshot, Config())
                self.assertFalse(any(item.rule == rule for item in findings))

    def test_cache_location_controls_do_not_change_semantic_identity(self):
        repo = make_repo({'app.py': b'x = 1\n'})
        self.addCleanup(repo.cleanup)
        head = repo.commit({'app.py': b'x = 2\n'})
        with tempfile.TemporaryDirectory() as one, tempfile.TemporaryDirectory() as two:
            first, _, _ = review(repo.root, repo.commit_ids[0], head, overrides={'cache_dir': one},
                                 exact_base=True, use_cache=False)
            second, _, _ = review(repo.root, repo.commit_ids[0], head, overrides={'cache_dir': two, 'use_cache': False},
                                  exact_base=True, use_cache=False)
            self.assertEqual(first.contract.config_digest, second.contract.config_digest)
            self.assertEqual(first.contract.expected_scope, second.contract.expected_scope)
            self.assertEqual(first.receipts, second.receipts)

    def test_cache_inside_reviewed_tree_not_admitted(self):
        repo = make_repo({'app.py': b'x = 1\n'})
        self.addCleanup(repo.cleanup)
        head = repo.commit({'app.py': b'x = 2\n'})
        with patch('pullraptor.kernel.load_facts', return_value=None) as load, patch('pullraptor.kernel.store_facts') as store:
            result, _, _ = review(repo.root, repo.commit_ids[0], head,
                                 overrides={'cache_dir': str(repo.root / 'cache')}, exact_base=True)
        self.assertEqual(result.execution['exit_code'], 0)
        load.assert_not_called()
        store.assert_not_called()

    def test_slow_preparation_short_policy_still_bounded(self):
        def stalled(*args, **kwargs):
            deadline = args[4]
            self.assertEqual(deadline.work_cutoff, start + 1)
            while not deadline.is_work_exhausted():
                time.sleep(.01)
            raise TimeoutError('trusted preparation control exhausted')
        start = time.monotonic()
        with patch('pullraptor.kernel.resolve_inputs', side_effect=stalled):
            result, deadline, _ = review(Path('.'), 'b', 'h', started_at=start, use_cache=False)
        self.assertLess(time.monotonic() - start, 1.5)
        self.assertEqual(result.kind, 'limit_failure')
        self.assertEqual(result.exit_code, 2)
        self.assertEqual(deadline.final_cutoff, start + 3)
        self.assertEqual(deadline.work_cutoff, start + 1)

    def test_both_present_python_sides_have_independent_scope_receipts(self):
        repo = make_repo({'app.py': b'import helper\n', 'helper.py': b'x=1\n'})
        self.addCleanup(repo.cleanup)
        head = repo.commit({'app.py': b'x=2\n'})
        value, _, _ = review(repo.root, repo.commit_ids[0], head, exact_base=True, use_cache=False)
        expected = {(item.snapshot, item.path) for item in value.contract.expected_scope}
        self.assertIn((repo.commit_ids[0], 'app.py'), expected)
        self.assertIn((repo.commit_ids[0], 'helper.py'), expected)
        self.assertIn((head, 'app.py'), expected)
        self.assertEqual({item.key for item in value.receipts}, {item.key for item in value.contract.expected_scope})

    def test_failed_discovery_cannot_seal_complete_scope(self):
        repo = make_repo({'app.py': b'x=1\n'})
        self.addCleanup(repo.cleanup)
        head = repo.commit({'app.py': b'def broken(:\n'})
        value, _, _ = review(repo.root, repo.commit_ids[0], head, exact_base=True, use_cache=False)
        self.assertEqual(value.execution['exit_code'], 2)
        self.assertFalse(value.contract.discovery_complete)
        self.assertTrue(any(item.status == 'incomplete' for item in value.receipts))

    def test_static_import_closure_cycles_and_unrelated_malformed_file(self):
        repo = make_repo({'app.py': b'import a\n', 'a.py': b'import b\n', 'b.py': b'import a\n',
                          'unrelated.py': b'def broken(:\n'})
        self.addCleanup(repo.cleanup)
        head = repo.commit({'app.py': b'import a\nx=2\n'})
        value, _, _ = review(repo.root, repo.commit_ids[0], head, exact_base=True, use_cache=False)
        required = {item.path for item in value.contract.expected_scope}
        self.assertTrue({'app.py', 'a.py', 'b.py'}.issubset(required))
        self.assertNotIn('unrelated.py', required)
        self.assertTrue(value.contract.discovery_complete)
        self.assertEqual(value.execution['exit_code'], 0)
