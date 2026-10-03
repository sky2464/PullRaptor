"""E04-A1 language worker result validation and dispatch tests."""

from __future__ import annotations

import inspect
import os
import sys
import time
import unittest
from pathlib import Path

from pullraptor.language_workers import (
    LanguageRegistry,
    LanguageRegistryEntry,
    LanguageRequest,
    LanguageResult,
    digest_executable_script,
    run_language,
    validate_worker_result,
)
from pullraptor.models import Deadline, Limits

_INERT_WORKER = Path(__file__).resolve().parent / "fixtures" / "languages" / "protocol" / "inert_worker.py"


def _inert_registry(*, grammar: str = "g1") -> LanguageRegistry:
    argv = (sys.executable, "-I", "-S", str(_INERT_WORKER))
    return LanguageRegistry(
        entries=(
            LanguageRegistryEntry(
                language="go",
                capability="syntax",
                executable_argv=argv,
                executable_digest=digest_executable_script(argv),
                grammar_digest=grammar,
                allowed_environment=(("PATH", os.environ.get("PATH", "")),),
                worker_cwd=str(_INERT_WORKER.parent),
            ),
        )
    )


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
        import pullraptor.language_workers as lw

        src = inspect.getsource(lw)
        self.assertNotIn("exec(", src)
        self.assertNotIn("eval(", src)
        self.assertNotIn("importlib.import_module", src)

    def test_timeout_has_gap(self) -> None:
        request = LanguageRequest("c1", ("x.py",), "python", "g1", "syntax", ())
        raw = LanguageResult("c1", (), (), ("timeout",), "g1")
        result = validate_worker_result(request, raw)
        self.assertIn("missing_receipt", result.unsupported)

    def test_run_language_inert_fixture_via_stdin(self) -> None:
        limits = Limits()
        deadline = Deadline(started_at=time.monotonic(), duration_seconds=30.0)
        request = LanguageRequest(
            contract_digest="contract-1",
            scope_keys=("sample.go",),
            language="go",
            grammar_digest="g1",
            capability="syntax",
            source_blobs=(("sample.go", b"package main\n"),),
        )
        result = run_language(
            request,
            registry=_inert_registry(),
            limits=limits,
            deadline=deadline,
        )
        self.assertEqual(result.contract_digest, "contract-1")
        self.assertEqual(result.completed_keys, ("sample.go",))
        self.assertEqual(result.producer_digest, "g1")
        self.assertEqual(result.unsupported, ())
        self.assertEqual(len(result.content_facts), 1)
        self.assertEqual(result.content_facts[0].get("path"), "sample.go")

    def test_run_language_registry_miss_has_gap(self) -> None:
        limits = Limits()
        deadline = Deadline(started_at=time.monotonic(), duration_seconds=10.0)
        request = LanguageRequest("c1", ("a.ts",), "typescript", "g1", "syntax", ())
        result = run_language(
            request,
            registry=_inert_registry(),
            limits=limits,
            deadline=deadline,
        )
        self.assertIn("registry_miss", result.unsupported)
        self.assertEqual(result.completed_keys, ())


if __name__ == "__main__":
    unittest.main()
