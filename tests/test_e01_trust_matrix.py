"""Independent input, evidence and location obligations for the E01 kernel."""
from dataclasses import replace
import hashlib
import os
from pathlib import Path
import time
import unittest
from unittest.mock import patch

from pullraptor.evidence import accumulate, align_findings, decide, validate_receipts
from pullraptor.models import Config, CoverageReceipt, Deadline, Evidence, Finding, Limits, ProcessResult, ReviewContract, ScopeEntry, Span
from pullraptor.python_facts import bind_facts, extract_python
from pullraptor.git_snapshot import read_snapshot
from pullraptor.diff import changes
from tests.helpers import make_repo


class EvidenceAuthority(unittest.TestCase):
    def contract(self):
        return ReviewContract("b", "b", "h", "p", "c", "t", "structural", (ScopeEntry("key", "file", "h", "python_structure"),), True)

    def finding(self, state="supported", side="head"):
        return Finding("PY001", "1.0", "mut_default", "x", Span("a.py", side, 1, 2, 0, 20, 1, 10), "literal pattern", "advisory", "blocker", state, "witness")

    def test_claim_type_is_independent(self):
        first = Evidence("k", "pattern", "context", True, False)
        with self.assertRaises(ValueError):
            accumulate((first, replace(first, claim_type="defect")))

    def test_same_claim_different_context_is_independent(self):
        first = Evidence("k", "pattern", "base", True, False)
        with self.assertRaises(ValueError):
            accumulate((first, replace(first, context="head")))

    def test_all_four_states_decisions(self):
        contract = self.contract()
        receipt = CoverageReceipt("key", "p", "python_structure", "complete")
        for state, code in (("unknown", 0), ("supported", 1), ("refuted", 0), ("conflicted", 0)):
            with self.subTest(state=state):
                self.assertEqual(decide(contract, (receipt,), (self.finding(state),), (), Config()), code)
                self.assertEqual(decide(replace(contract, discovery_complete=False), (receipt,), (self.finding(state),), (), Config()), 2)

    def test_policy_does_not_depend_on_worker_supplied_diagnostics(self):
        for receipt in (CoverageReceipt("key", "old", "python_structure", "complete"), CoverageReceipt("key", "p", "foreign_capability", "complete"), CoverageReceipt("foreign", "p", "python_structure", "complete")):
            with self.subTest(receipt=receipt):
                self.assertEqual(decide(self.contract(), (receipt,), (), (), Config()), 2)

    def test_duplicate_coordinator_scope_cannot_complete(self):
        contract = self.contract()
        contract = replace(contract, expected_scope=contract.expected_scope * 2)
        receipt = CoverageReceipt("key", "p", "python_structure", "complete")
        self.assertTrue(validate_receipts(contract, (receipt,)))
        self.assertEqual(decide(contract, (receipt,), (), (), Config()), 2)

    def test_ambiguous_baseline_alignment_is_unknown(self):
        first = self.finding(side="base")
        aligned = align_findings((first, replace(first, witness="different")), (self.finding(),))
        self.assertEqual(aligned[0].delta, "unknown")
        self.assertEqual(aligned[0].evidence_delta, "unknown")

    def test_deleted_findings_remain_baseline_history(self):
        first = self.finding(side="base")
        history = align_findings((first,), ())
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].span.side, "base")
        self.assertEqual(history[0].delta, "no_longer_detected")


class ImmutableInputs(unittest.TestCase):
    def setUp(self):
        self.repo = make_repo({"a.py": b"x=1\n"})
    def tearDown(self):
        self.repo.cleanup()
    def deadline(self):
        return Deadline(time.monotonic(), 30)

    def test_snapshot_partial_output_never_admitted(self):
        result = ProcessResult(0, b"100644 blob " + b"a" * 40 + b" 4\ta.py\0", b"", 0, stdout_truncated=True)
        with patch("pullraptor.git_snapshot.run_bounded", return_value=result), self.assertRaises(ValueError):
            read_snapshot(self.repo.root, self.repo.commit_ids[0], Limits(), self.deadline())

    def test_snapshot_malformed_record_never_omitted(self):
        for raw in (b"invalid\0", b"100644 blob nope 4\ta.py\0"):
            with self.subTest(raw=raw), patch("pullraptor.git_snapshot.run_bounded", return_value=ProcessResult(0, raw, b"", 0)), self.assertRaises(ValueError):
                read_snapshot(self.repo.root, self.repo.commit_ids[0], Limits(), self.deadline())

    def test_aggregate_diff_failure_is_visible(self):
        base = self.repo.commit_ids[0]
        head = self.repo.commit({"a.py": b"x=2\n" * 100})
        before = read_snapshot(self.repo.root, base, Limits(), self.deadline())
        after = read_snapshot(self.repo.root, head, Limits(), self.deadline())
        with self.assertRaises((ValueError, TimeoutError)):
            changes(self.repo.root, before, after, Limits(max_diff_bytes=32), self.deadline())

    def test_bound_coordinates_validate_actual_source(self):
        source = b"def f(x=[]):\n    x.append(1)\n"
        result = extract_python(source, Limits(), self.deadline())
        self.assertIsNotNone(result.content)
        bad = dict(result.content.pattern_facts[0])
        bad["coords"] = {**bad["coords"], "end_byte": len(source) + 100}
        snapshot = read_snapshot(self.repo.root, self.repo.commit({"a.py": source}), Limits(), self.deadline())
        with self.assertRaises(ValueError):
            bind_facts(replace(result.content, pattern_facts=(bad,)), source, snapshot, "a.py", "head")

    def test_source_unicode_crlf_span_and_occurrence(self):
        source = "# 🚀\r\nimport subprocess as sp\r\nsp.run('é', shell=True)\r\n".encode()
        parsed = extract_python(source, Limits(), self.deadline())
        fact = parsed.content.pattern_facts[0]
        span = fact["coords"]
        start = source.index(b"sp.run")
        end = source.index(b")", start) + 1
        self.assertEqual(span, {"start_line": 3, "end_line": 3, "start_byte": start, "end_byte": end, "start_column": 1, "end_column": len("sp.run('é', shell=True)") + 1})
        head = self.repo.commit({"a.py": source, "other.py": source})
        snapshot = read_snapshot(self.repo.root, head, Limits(), self.deadline())
        a = bind_facts(parsed.content, source, snapshot, "a.py", "base")
        b = bind_facts(parsed.content, source, snapshot, "other.py", "head")
        self.assertEqual((a.snapshot, a.path, a.side), (head, "a.py", "base"))
        self.assertEqual((b.snapshot, b.path, b.side), (head, "other.py", "head"))
        self.assertIs(a.content, b.content)
