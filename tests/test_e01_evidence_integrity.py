"""Adverse evidence integrity checks; aggregate success is not a criterion receipt."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from scripts.e01_build_requirement_map import assertion_inventory, source_identity
from scripts.e01_validate_requirement_map import validate_map


class EvidenceIntegrityTests(unittest.TestCase):
    def test_body_inventory_contains_exact_assertions_not_declarations(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'tests').mkdir()
            (root / 'tests/test_example.py').write_text(
                'class Checks:\n    def test_real(self):\n        self.assertEqual(actual, expected)\n'
                '    def test_name_only(self):\n        pass\n')
            entries = assertion_inventory(root)
            self.assertEqual(len(entries), 1)
            item = entries[0]
            self.assertEqual(item['test_id'], 'tests.test_example.Checks.test_real')
            self.assertEqual(item['assertions'][0]['line'], 3)
            self.assertEqual(item['assertions'][0]['expression'], 'self.assertEqual(actual, expected)')
            self.assertEqual(len(item['body_sha256']), 64)

    def test_runtime_pass_requires_matching_case_receipt_and_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'src').mkdir()
            (root / 'src/core.py').write_text('value = 1\n')
            (root / 'tests').mkdir()
            (root / 'tests/test_example.py').write_text('class Checks:\n    def test_real(self):\n        self.assertEqual(actual, expected)\n')
            body = assertion_inventory(root)[0]
            source = source_identity(root)
            row = {'requirement_id': 'R1', 'assertion_coverage': 'mapped', 'runtime_result': 'passed',
                   'primary_assertions': [body], 'remaining_gap': ''}
            data = {'product_source': source, 'named_requirements': [row],
                    'unnamed_requirements': [], 'evaluation_invariants': [],
                    'acceptance_criteria': {'independent_decision': 'pending'}}
            receipt = {'product_source': source, 'cases': [{**body, 'result': 'passed'}]}
            self.assertEqual(validate_map(data, root, receipt), [])
            self.assertTrue(validate_map(data, root, None))
            forged = deepcopy(receipt)
            forged['cases'][0]['result'] = 'failed'
            self.assertTrue(validate_map(data, root, forged))
            (root / 'src/core.py').write_text('value = 2\n')
            self.assertTrue(validate_map(data, root, receipt))

    def test_body_change_invalidates_pass_even_when_test_name_survives(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'src').mkdir()
            (root / 'tests').mkdir()
            test = root / 'tests/test_example.py'
            test.write_text('class Checks:\n    def test_real(self):\n        self.assertEqual(actual, expected)\n')
            body = assertion_inventory(root)[0]
            source = source_identity(root)
            data = {'product_source': source, 'named_requirements': [{'requirement_id': 'R1',
                    'assertion_coverage': 'mapped', 'runtime_result': 'passed', 'primary_assertions': [body],
                    'remaining_gap': ''}], 'unnamed_requirements': [], 'evaluation_invariants': [],
                    'acceptance_criteria': {'independent_decision': 'pending'}}
            receipt = {'product_source': source, 'cases': [{**body, 'result': 'passed'}]}
            test.write_text('class Checks:\n    def test_real(self):\n        self.assertEqual(actual, different)\n')
            self.assertTrue(validate_map(data, root, receipt))

    def test_partial_coverage_cannot_earn_runtime_pass(self):
        data = {'product_source': source_identity(Path('.')), 'named_requirements': [
            {'requirement_id': 'R1', 'assertion_coverage': 'partial', 'runtime_result': 'passed',
             'primary_assertions': [], 'remaining_gap': 'no adverse case'}],
            'unnamed_requirements': [], 'evaluation_invariants': [], 'acceptance_criteria': {'independent_decision': 'pending'}}
        self.assertTrue(validate_map(data, Path('.'), {'product_source': data['product_source'], 'cases': []}))

    def test_collector_records_failure_skip_and_subtest_separately(self):
        from scripts.e01_refresh_acceptance_evidence import collect_suite
        class Cases(unittest.TestCase):
            def test_pass(self): self.assertEqual(2, 2)
            def test_fail(self): self.assertEqual(2, 3)
            def test_skip(self): self.skipTest('required control absent')
            def test_subtests(self):
                for value in (1, 2):
                    with self.subTest(value=value): self.assertEqual(value, 1)
        cases, _ = collect_suite(unittest.defaultTestLoader.loadTestsFromTestCase(Cases))
        by_name = {item['test_id'].split('.')[-1]: item for item in cases}
        self.assertEqual(by_name['test_pass']['result'], 'passed')
        self.assertEqual(by_name['test_fail']['result'], 'failed')
        self.assertEqual(by_name['test_skip']['result'], 'not_run')
        self.assertEqual(by_name['test_subtests']['result'], 'failed')
        self.assertEqual(len(by_name['test_subtests']['subcases']), 2)
        self.assertEqual(by_name['test_subtests']['subcases'][1]['result'], 'failed')
