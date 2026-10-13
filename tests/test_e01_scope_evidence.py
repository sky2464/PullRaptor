"""Exhaustive state decisions and coordinator-owned scope rejection cases."""
from dataclasses import replace
import unittest
from pullraptor.evidence import accumulate, align_findings, decide, validate_receipts
from pullraptor.models import Config, CoverageReceipt, Evidence, Finding, ReviewContract, ScopeEntry, Span


def contract():
    return ReviewContract('base', 'base', 'head', 'policy', 'config', 'tool', 'structural',
                         (ScopeEntry('file:head:6170702e7079:python_patterns', 'file', 'head', 'python_patterns',
                                     path='app.py', path_bytes=b'app.py'),), True)


def finding(state='supported', side='head', path='app.py'):
    return Finding('PY001', '1.0', 'mutation', 'x', Span(path, side, 1, 1, 0, 1, 1, 2),
                   'Pattern observation', 'advisory', 'blocker', state, 'x.append(1)')


class ScopeEvidenceTests(unittest.TestCase):
    def test_exhaustive_four_state_policy_decisions(self):
        request = contract()
        receipt = CoverageReceipt(request.expected_scope[0].key, 'policy', 'python_patterns', 'complete')
        for state, expected in (('undetermined', 0), ('supported', 1), ('refuted', 0), ('conflicted', 0)):
            with self.subTest(state=state):
                self.assertEqual(decide(request, (receipt,), (finding(state),), (), Config()), expected)
                self.assertEqual(decide(replace(request, discovery_complete=False), (receipt,), (finding(state),), (), Config()), 2)

    def test_same_key_context_different_claim_type_cannot_accumulate(self):
        pattern = Evidence('claim', 'pattern', 'context', True, False)
        defect = Evidence('claim', 'defect', 'context', True, False)
        with self.assertRaises(ValueError): accumulate((pattern, defect))

    def test_each_missing_duplicate_foreign_revision_capability_receipt_rejected(self):
        request = contract()
        receipt = CoverageReceipt(request.expected_scope[0].key, 'policy', 'python_patterns', 'complete')
        cases = ((), (receipt, receipt), (replace(receipt, key='foreign'),),
                 (replace(receipt, contract_digest='different'),),
                 (replace(receipt, key='file:old:6170702e7079:python_patterns'),),
                 (replace(receipt, capability='different'),))
        for receipts in cases:
            with self.subTest(receipts=receipts):
                diagnostics = validate_receipts(request, receipts)
                self.assertTrue(diagnostics)
                self.assertEqual(decide(request, receipts, (), diagnostics, Config()), 2)
        self.assertEqual(validate_receipts(request, (receipt,)), ())

    def test_worker_cannot_shrink_coordinator_scope(self):
        request = contract()
        diagnostics = validate_receipts(request, ())
        self.assertTrue(any(item.code == 'MISSING_RECEIPT' for item in diagnostics))
        self.assertEqual(decide(request, (), (), diagnostics, Config()), 2)
        self.assertEqual(len(request.expected_scope), 1)

    def test_valid_head_claim_survives_unrelated_partial_scope(self):
        request = contract()
        receipt = CoverageReceipt(request.expected_scope[0].key, 'policy', 'python_patterns', 'incomplete',
                                  cause='unrelated_fixture_failure')
        aligned = align_findings((), (finding(),), comparable=False)
        self.assertEqual(len(aligned), 1)
        self.assertEqual(aligned[0].state, 'supported')
        self.assertEqual(aligned[0].delta, 'unknown')
        self.assertEqual(decide(request, (receipt,), aligned, (), Config()), 2)

    def test_no_longer_detected_preserves_baseline_side_and_never_claims_fixed(self):
        baseline = replace(finding(side='base'), policy_class='advisory')
        aligned = align_findings((baseline,), (), comparable=True)
        self.assertEqual(len(aligned), 1)
        self.assertEqual(aligned[0].delta, 'no_longer_detected')
        self.assertEqual(aligned[0].span.side, 'base')
        self.assertEqual(aligned[0].state, 'supported')
        self.assertNotIn('fixed', aligned[0].claim.lower())

    def test_duplicate_alignment_obligations_remain_unknown(self):
        baseline = replace(finding(side='base'), policy_class='advisory')
        aligned = align_findings((baseline, replace(baseline, witness='other mutation')), (finding(),), comparable=True)
        self.assertEqual(aligned[0].delta, 'unknown')
        self.assertEqual(aligned[0].evidence_delta, 'unknown')
