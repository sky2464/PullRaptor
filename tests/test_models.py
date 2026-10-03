"""Tests for PullRaptor models, bounded codec, and canonical output."""

import json
import time
import unittest

from pullraptor.models import (
    BlobRef,
    BoundFacts,
    Change,
    Config,
    ContentFacts,
    CoverageReceipt,
    Deadline,
    Diagnostic,
    Evidence,
    FactResult,
    Finding,
    FullReport,
    LimitFailure,
    Limits,
    ProcessBounds,
    ProcessResult,
    RecordLimits,
    ResolvedFacts,
    ReviewContract,
    ScopeEntry,
    Snapshot,
    Span,
    canonical_bytes,
    decode_record,
    encode_record,
    file_scope_key,
    import_scope_key,
)


class TestModels(unittest.TestCase):
    def setUp(self) -> None:
        self.limits = Limits()
        self.record_limits = RecordLimits()
        now = time.monotonic()
        self.deadline = Deadline(started_at=now, duration_seconds=60.0, reserve_seconds=2.0)

    def _make_sample_contract(self) -> ReviewContract:
        scope = (
            ScopeEntry(
                key=file_scope_key("file", "head123", b"src/app.py", "python_patterns"),
                kind="file",
                snapshot="head123",
                capability="python_patterns",
                path="src/app.py",
                path_bytes=b"src/app.py",
                reason="changed source",
            ),
        )
        return ReviewContract(
            base_tip="base123",
            comparison_base="base123",
            head="head123",
            policy_digest="pol123",
            config_digest="cfg123",
            tool_digest="tool123",
            profile="structural",
            expected_scope=scope,
            discovery_complete=True,
        )

    def _make_sample_report(self, execution_metadata: dict[str, object] | None = None) -> FullReport:
        contract = self._make_sample_contract()
        receipts = (
            CoverageReceipt(
                key=contract.expected_scope[0].key,
                contract_digest="pol123",
                capability="python_patterns",
                status="complete",
                cause=None,
                recovery=None,
            ),
        )
        span = Span(
            path="src/app.py",
            side="head",
            start_line=10,
            end_line=12,
            start_byte=100,
            end_byte=150,
            start_column=1,
            end_column=20,
        )
        findings = (
            Finding(
                rule="PY001",
                version="1.0",
                obligation="mut_default",
                anchor="foo",
                span=span,
                claim="Default object can persist across omitted-argument calls",
                severity="advisory",
                policy_class="advisory",
                state="supported",
                witness="def foo(x=[]): x.append(1)",
                assumptions=("no intentional caching",),
                delta="newly_detected",
                evidence_delta="added",
            ),
        )
        return FullReport(
            schema="1",
            kind="full",
            contract=contract,
            receipts=receipts,
            inventory=("src/app.py",),
            exclusions=(),
            findings=findings,
            diagnostics=(),
            execution=execution_metadata or {"duration_ms": 120, "cache_hit": True, "cache_dir": "/tmp/cache"},
        )

    def test_canonical_excludes_execution_metadata(self) -> None:
        """Duration/cache admission/hit/location changes leave canonical bytes identical;

        coverage/witness changes do not.
        """
        report1 = self._make_sample_report({"duration_ms": 100, "cache_hit": False, "cache_dir": "/tmp/cache1"})
        report2 = self._make_sample_report({"duration_ms": 450, "cache_hit": True, "cache_dir": "/var/cache2"})

        bytes1 = canonical_bytes(report1, limits=self.record_limits, deadline=self.deadline)
        bytes2 = canonical_bytes(report2, limits=self.record_limits, deadline=self.deadline)
        self.assertEqual(bytes1, bytes2)

        # But changing a witness changes canonical bytes
        finding_modified = Finding(
            rule="PY001",
            version="1.0",
            obligation="mut_default",
            anchor="foo",
            span=report1.findings[0].span,
            claim="Default object can persist across omitted-argument calls",
            severity="advisory",
            policy_class="advisory",
            state="supported",
            witness="different witness text",
            assumptions=("no intentional caching",),
            delta="newly_detected",
            evidence_delta="added",
        )
        report3 = FullReport(
            schema="1",
            kind="full",
            contract=report1.contract,
            receipts=report1.receipts,
            inventory=report1.inventory,
            exclusions=report1.exclusions,
            findings=(finding_modified,),
            diagnostics=report1.diagnostics,
            execution=report1.execution,
        )
        bytes3 = canonical_bytes(report3, limits=self.record_limits, deadline=self.deadline)
        self.assertNotEqual(bytes1, bytes3)

    def test_invalid_span_rejected(self) -> None:
        # line must be >= 1
        with self.assertRaises(ValueError):
            Span(
                path="a.py", side="head",
                start_line=0, end_line=1,
                start_byte=0, end_byte=10,
                start_column=1, end_column=5,
            )
        # start_line > end_line
        with self.assertRaises(ValueError):
            Span(
                path="a.py", side="head",
                start_line=5, end_line=2,
                start_byte=0, end_byte=10,
                start_column=1, end_column=5,
            )
        # negative start_byte
        with self.assertRaises(ValueError):
            Span(
                path="a.py", side="head",
                start_line=1, end_line=2,
                start_byte=-1, end_byte=10,
                start_column=1, end_column=5,
            )
        # start_byte > end_byte
        with self.assertRaises(ValueError):
            Span(
                path="a.py", side="head",
                start_line=1, end_line=2,
                start_byte=20, end_byte=10,
                start_column=1, end_column=5,
            )
        # column < 1
        with self.assertRaises(ValueError):
            Span(
                path="a.py", side="head",
                start_line=1, end_line=2,
                start_byte=0, end_byte=10,
                start_column=0, end_column=5,
            )
        # invalid side
        with self.assertRaises(ValueError):
            Span(
                path="a.py", side="other",
                start_line=1, end_line=2,
                start_byte=0, end_byte=10,
                start_column=1, end_column=5,
            )

    def test_content_facts_cannot_carry_occurrence(self) -> None:
        """ContentFacts must not accept path or side."""
        # ContentFacts has no path or side attributes
        cf = ContentFacts(
            blob_digest="abc12345",
            runtime_version="3.12.15",
            schema_version="1",
            extractor_digest="ext123",
            symbols=(),
            imports=(),
            pattern_facts=(),
            unsupported_constructs=(),
            relative_locations=(),
        )
        self.assertFalse(hasattr(cf, "path"))
        self.assertFalse(hasattr(cf, "side"))
        self.assertFalse(hasattr(cf, "snapshot"))
        with self.assertRaises(TypeError):
            ContentFacts(  # type: ignore
                blob_digest="abc12345",
                runtime_version="3.12.15",
                schema_version="1",
                extractor_digest="ext123",
                symbols=(),
                imports=(),
                pattern_facts=(),
                unsupported_constructs=(),
                relative_locations=(),
                path="foo.py",
            )

    def test_duplicate_keys_rejected(self) -> None:
        payload = b'{"a": 1, "a": 2}'
        with self.assertRaises(ValueError) as ctx:
            decode_record(payload, schema="any", limits=self.record_limits)
        self.assertIn("duplicate", str(ctx.exception).lower())

    def test_nonfinite_json_rejected(self) -> None:
        for bad in (b'{"a": NaN}', b'{"a": Infinity}', b'{"a": -Infinity}'):
            with self.assertRaises(ValueError):
                decode_record(bad, schema="any", limits=self.record_limits)

    def test_bool_not_integer(self) -> None:
        # If schema expects int, bool must be rejected
        payload = b'{"line": true}'
        with self.assertRaises(ValueError) as ctx:
            decode_record(payload, schema="span", limits=self.record_limits)
        self.assertIn("boolean", str(ctx.exception).lower())

    def test_max_payload_bytes_rejected(self) -> None:
        limits = RecordLimits(max_payload_bytes=20)
        payload = b'{"message": "this payload is too long"}'
        with self.assertRaises(ValueError) as ctx:
            decode_record(payload, schema="any", limits=limits)
        self.assertIn("payload", str(ctx.exception).lower())

    def test_max_depth_rejected(self) -> None:
        limits = RecordLimits(max_depth=3)
        # Depth 4: {"a": {"b": {"c": {"d": 1}}}}
        payload = b'{"a": {"b": {"c": {"d": 1}}}}'
        with self.assertRaises(ValueError) as ctx:
            decode_record(payload, schema="any", limits=limits)
        self.assertIn("depth", str(ctx.exception).lower())

    def test_max_aggregate_items_rejected(self) -> None:
        limits = RecordLimits(max_aggregate_items=3)
        # payload with 4 items: 2 in list + list + root object = 4
        payload = b'{"items": [1, 2, 3]}'
        with self.assertRaises(ValueError) as ctx:
            decode_record(payload, schema="any", limits=limits)
        self.assertIn("item", str(ctx.exception).lower())

    def test_max_string_bytes_rejected(self) -> None:
        limits = RecordLimits(max_string_bytes=5)
        payload = b'{"key": "toolongstring"}'
        with self.assertRaises(ValueError) as ctx:
            decode_record(payload, schema="any", limits=limits)
        self.assertIn("string", str(ctx.exception).lower())

    def test_malformed_utf8_rejected(self) -> None:
        payload = b'{"key": "\xff\xfe"}'
        with self.assertRaises(ValueError):
            decode_record(payload, schema="any", limits=self.record_limits)

    def test_surrogate_rejected(self) -> None:
        # \ud800 is an unpaired surrogate
        payload = b'{"key": "\\ud800"}'
        with self.assertRaises(ValueError):
            decode_record(payload, schema="any", limits=self.record_limits)

    def test_report_union_strict_tags(self) -> None:
        payload = b'{"schema": "1", "kind": "unknown_variant"}'
        with self.assertRaises(ValueError) as ctx:
            decode_record(payload, schema="report", limits=self.record_limits)
        self.assertIn("kind", str(ctx.exception).lower())

    def test_item_accounting_recursive(self) -> None:
        # Test that item accounting counts nested object members and array elements recursively
        limits = RecordLimits(max_aggregate_items=5)
        # {"a": [1, 2], "b": 3}:
        # dict has 2 key-value pairs (2 items), inner list has 2 items -> 4 total items
        payload = b'{"a": [1, 2], "b": 3}'
        record = decode_record(payload, schema="any", limits=limits)
        self.assertEqual(record["b"], 3)

        # Exceeding 5 items:
        payload_too_many = b'{"a": [1, 2, 3], "b": {"c": 4}}'
        with self.assertRaises(ValueError) as ctx:
            decode_record(payload_too_many, schema="any", limits=limits)
        self.assertIn("item", str(ctx.exception).lower())

    def test_limit_failure_cannot_claim_support_or_complete(self) -> None:
        lf = LimitFailure(
            schema="1",
            kind="limit_failure",
            known_inputs={
                "base_tip": "base123",
                "comparison_base": "base123",
                "head": "head123",
                "policy_digest": "pol123",
                "reviewer_digest": "rev123",
            },
            exit_code=2,
            analysis_complete=False,
            details_omitted=True,
            cause="byte_limit_exceeded",
            limit={"name": "max_blob_bytes", "cap": 2097152, "observed": 3000000},
            omitted_domains=({"domain": "findings", "count": None},),
        )
        self.assertEqual(lf.exit_code, 2)
        self.assertFalse(lf.analysis_complete)
        self.assertTrue(lf.details_omitted)
        self.assertFalse(hasattr(lf, "findings"))
        self.assertFalse(hasattr(lf, "support"))
        self.assertFalse(hasattr(lf, "publishable"))

        # Cannot create with exit_code != 2 or analysis_complete != False
        with self.assertRaises(ValueError):
            LimitFailure(
                schema="1",
                kind="limit_failure",
                known_inputs={},
                exit_code=0,
                analysis_complete=False,
                details_omitted=True,
                cause="byte_limit_exceeded",
                limit=None,
                omitted_domains=(),
            )

        with self.assertRaises(ValueError):
            LimitFailure(
                schema="1",
                kind="limit_failure",
                known_inputs={},
                exit_code=2,
                analysis_complete=True,
                details_omitted=True,
                cause="byte_limit_exceeded",
                limit=None,
                omitted_domains=(),
            )

    def test_two_missing_imports_have_distinct_keys(self) -> None:
        key1 = import_scope_key(
            kind="import_lookup",
            snapshot="head123",
            source_occurrence="src/app.py:1:1",
            canonical_target="os_helper",
            relative_level=0,
            capability="python_structure",
        )
        key2 = import_scope_key(
            kind="import_lookup",
            snapshot="head123",
            source_occurrence="src/app.py:2:1",
            canonical_target="net_helper",
            relative_level=0,
            capability="python_structure",
        )
        self.assertNotEqual(key1, key2)

    def test_roundtrip_full_report(self) -> None:
        report = self._make_sample_report()
        encoded = canonical_bytes(report, limits=self.record_limits, deadline=self.deadline)
        decoded = decode_record(encoded, schema="report", limits=self.record_limits)
        self.assertEqual(decoded["schema"], "1")
        self.assertEqual(decoded["kind"], "full")
        self.assertEqual(len(decoded["findings"]), 1)
        self.assertEqual(decoded["findings"][0]["rule"], "PY001")

    def test_roundtrip_limit_failure(self) -> None:
        lf = LimitFailure(
            schema="1",
            kind="limit_failure",
            known_inputs={"base_tip": "b1", "comparison_base": "b1", "head": "h1", "policy_digest": None, "reviewer_digest": None},
            exit_code=2,
            analysis_complete=False,
            details_omitted=True,
            cause="deadline_exceeded",
            limit={"name": "review_timeout_seconds", "cap": 60.0, "observed": 60.5},
            omitted_domains=({"domain": "findings", "count": None},),
        )
        encoded = canonical_bytes(lf, limits=self.record_limits, deadline=self.deadline)
        self.assertLessEqual(len(encoded), 16384)
        decoded = decode_record(encoded, schema="report", limits=self.record_limits)
        self.assertEqual(decoded["schema"], "1")
        self.assertEqual(decoded["kind"], "limit_failure")
        self.assertEqual(decoded["exit_code"], 2)
        self.assertFalse(decoded["analysis_complete"])

    def test_prohibit_unknown_authority_fields(self) -> None:
        # Unknown fields in report or contract must be rejected
        payload = b'{"schema": "1", "kind": "full", "unauthorized_admin": true}'
        with self.assertRaises(ValueError):
            decode_record(payload, schema="report", limits=self.record_limits)


if __name__ == "__main__":
    unittest.main()
