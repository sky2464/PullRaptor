"""E04-A1 language worker result validation tests."""

from __future__ import annotations

import unittest

from pullraptor.language_workers import LanguageRequest, LanguageResult, validate_worker_result


class TestLanguageWorkers(unittest.TestCase):
    def test_omitted_foreign_duplicate_receipts_partial(self) -> None:
        request = LanguageRequest(
            contract_digest="c1",
            scope_keys=("a.py", "b.py"),
            language="go",
            grammar_digest="g1",
            capability="syntax",
            source_blobs=(),
        )
        raw = LanguageResult(
            contract_digest="c1",
            completed_keys=("a.py",),
            content_facts=({"capability": "syntax", "path": "a.py"},),
            unsupported=(),
            producer_digest="g1",
        )
        result = validate_worker_result(request, raw)
        missing_key = "b.py"
        self.assertNotIn(missing_key, result.completed_keys)
        self.assertIn("missing_receipt", result.unsupported)

    def test_worker_cannot_advertise_extra_capability(self) -> None:
        request = LanguageRequest("c1", ("f.js",), "typescript", "g1", "syntax", ())
        raw = LanguageResult(
            "c1",
            ("f.js",),
            ({"capability": "cfg", "path": "f.js"},),
            (),
            "g1",
        )
        result = validate_worker_result(request, raw)
        self.assertIn("extra_capability", result.unsupported)

    def test_grammar_config_change_invalidates_cache(self) -> None:
        request = LanguageRequest("c1", ("f.go",), "go", "g1", "syntax", ())
        raw = LanguageResult("c1", ("f.go",), (), (), "g2")
        result = validate_worker_result(request, raw)
        self.assertIn("grammar_config_change", result.unsupported)

    def test_source_not_executed(self) -> None:
        # Validation is pure; no subprocess import side effects in this module.
        import pullraptor.language_workers as lw

        self.assertNotIn("run_bounded", lw.__dict__)

    def test_timeout_has_gap(self) -> None:
        request = LanguageRequest("c1", ("x.py",), "python", "g1", "syntax", ())
        raw = LanguageResult("c1", (), (), ("timeout",), "g1")
        result = validate_worker_result(request, raw)
        self.assertIn("missing_receipt", result.unsupported)


if __name__ == "__main__":
    unittest.main()
