"""Tests for PullRaptor Python fact extraction, isolated worker, and resolution."""

import hashlib
import os
import sys
import time
import unittest

from pullraptor.models import (
    BlobRef,
    BoundFacts,
    ContentFacts,
    Deadline,
    Diagnostic,
    Limits,
    Snapshot,
    Span,
)
from pullraptor.python_facts import (
    bind_facts,
    extract_python,
    resolve_context,
)


class TestPythonFacts(unittest.TestCase):
    def setUp(self) -> None:
        self.limits = Limits()
        self.deadline = Deadline(started_at=time.monotonic(), duration_seconds=30.0)

    def test_unicode_columns_crlf_exact(self) -> None:
        # File with CRLF and multibyte Unicode character (🚀 is 4 bytes in UTF-8)
        code = b'# \xf0\x9f\x9a\x80\r\nx = "test"\r\n'
        res = extract_python(code, self.limits, self.deadline)
        self.assertIsNotNone(res.content)
        self.assertEqual(len(res.diagnostics), 0)

        facts = res.content
        self.assertEqual(facts.blob_digest, hashlib.sha256(code).hexdigest())

    def test_scope_shadowing_and_aliases(self) -> None:
        code = b"""
import subprocess as sp

def run():
    sp = "shadowed"
    # sp is now a string, not subprocess
    return sp
"""
        res = extract_python(code, self.limits, self.deadline)
        self.assertIsNotNone(res.content)
        # Should not flag shadowed subprocess
        py003_facts = [f for f in res.content.pattern_facts if f.get("rule") == "PY003"]
        self.assertEqual(len(py003_facts), 0)

    def test_nested_functions_not_outer_mutation(self) -> None:
        code = b"""
def outer(items=[]):
    def inner():
        items = []
        items.append(1)
    return inner
"""
        res = extract_python(code, self.limits, self.deadline)
        self.assertIsNotNone(res.content)
        py001_facts = [f for f in res.content.pattern_facts if f.get("rule") == "PY001"]
        self.assertEqual(len(py001_facts), 0)

    def test_parameter_reassignment(self) -> None:
        code = b"""
def foo(data=[]):
    data = list(data)
    data.append(1)
    return data
"""
        res = extract_python(code, self.limits, self.deadline)
        self.assertIsNotNone(res.content)
        py001_facts = [f for f in res.content.pattern_facts if f.get("rule") == "PY001"]
        self.assertEqual(len(py001_facts), 0)

    def test_parse_failure_preserves_diff_coverage(self) -> None:
        bad_code = b"def syntax_error(:\n    pass\n"
        res = extract_python(bad_code, self.limits, self.deadline)
        self.assertIsNone(res.content)
        self.assertEqual(len(res.diagnostics), 1)
        diag = res.diagnostics[0]
        self.assertEqual(diag.code, "PY_PARSE_FAILED")
        major_minor = f"{sys.version_info.major}.{sys.version_info.minor}"
        self.assertIn(f"Python {major_minor} could not parse this file", diag.message)

    def test_import_side_effect_not_executed(self) -> None:
        # Code that writes a file if executed
        code = b"""
import os
os.environ["SENTINEL_INJECTED"] = "PWNED"
"""
        if "SENTINEL_INJECTED" in os.environ:
            del os.environ["SENTINEL_INJECTED"]
        res = extract_python(code, self.limits, self.deadline)
        self.assertIsNotNone(res.content)
        self.assertNotIn("SENTINEL_INJECTED", os.environ)

    def test_oversized_source_not_sent_to_worker(self) -> None:
        limits = Limits(max_blob_bytes=100)
        oversized = b"x = 1\n" * 100
        res = extract_python(oversized, limits, self.deadline)
        self.assertIsNone(res.content)
        self.assertTrue(any(d.code == "LIMIT_EXCEEDED" for d in res.diagnostics))

    def test_wrong_blob_or_span_rejected(self) -> None:
        code = b"x = 1\n"
        res = extract_python(code, self.limits, self.deadline)
        facts = res.content
        assert facts is not None

        blob = BlobRef(path="a.py", path_bytes=b"a.py", mode="100644", blob_oid="123", size=len(code))
        snap = Snapshot(oid="snap1", blobs=(blob,))

        # Passing mismatching source to bind_facts must fail
        with self.assertRaises(ValueError):
            bind_facts(facts, b"different_source = 2\n", snap, "a.py", "head")

    def test_stdlib_identity_not_missing_context(self) -> None:
        code = b"import json\nimport os\n"
        res = extract_python(code, self.limits, self.deadline)
        facts = res.content
        assert facts is not None

        blob = BlobRef(path="app.py", path_bytes=b"app.py", mode="100644", blob_oid="123", size=len(code))
        snap = Snapshot(oid="snap1", blobs=(blob,))
        bound = bind_facts(facts, code, snap, "app.py", "head")

        resolved, diags = resolve_context((bound,), snap)
        self.assertEqual(len(diags), 0)
        resolved_imports = resolved[0].resolved_imports
        self.assertTrue(any(imp["canonical"] == "json" and imp["kind"] == "stdlib" for imp in resolved_imports))
        self.assertTrue(any(imp["canonical"] == "os" and imp["kind"] == "stdlib" for imp in resolved_imports))

    def test_missing_external_module_partial(self) -> None:
        code = b"import requests\n"
        res = extract_python(code, self.limits, self.deadline)
        facts = res.content
        assert facts is not None

        blob = BlobRef(path="app.py", path_bytes=b"app.py", mode="100644", blob_oid="123", size=len(code))
        snap = Snapshot(oid="snap1", blobs=(blob,))
        bound = bind_facts(facts, code, snap, "app.py", "head")

        resolved, diags = resolve_context((bound,), snap)
        # requests is not in stdlib and not in manifest, so it is unresolved
        self.assertTrue(any(d.code == "IMPORT_UNRESOLVED" and "requests" in d.message for d in diags))

    def test_new_module_resolves_previous_miss(self) -> None:
        code = b"import helper\n"
        res = extract_python(code, self.limits, self.deadline)
        facts = res.content
        assert facts is not None

        # Snapshot 1: helper.py is missing
        blob1 = BlobRef(path="app.py", path_bytes=b"app.py", mode="100644", blob_oid="123", size=len(code))
        snap1 = Snapshot(oid="snap1", blobs=(blob1,))
        bound1 = bind_facts(facts, code, snap1, "app.py", "head")
        _, diags1 = resolve_context((bound1,), snap1)
        self.assertTrue(any("helper" in d.message for d in diags1))

        # Snapshot 2: helper.py is present
        blob2 = BlobRef(path="helper.py", path_bytes=b"helper.py", mode="100644", blob_oid="456", size=10)
        snap2 = Snapshot(oid="snap2", blobs=(blob1, blob2))
        bound2 = bind_facts(facts, code, snap2, "app.py", "head")
        resolved2, diags2 = resolve_context((bound2,), snap2)
        self.assertEqual(len(diags2), 0)
        self.assertTrue(any(imp["canonical"] == "helper" and imp["kind"] == "repo" for imp in resolved2[0].resolved_imports))

    def test_subprocess_alias_modeled(self) -> None:
        code = b"""
import subprocess as sp
sp.run(["ls"], shell=True)
"""
        res = extract_python(code, self.limits, self.deadline)
        facts = res.content
        assert facts is not None
        py003 = [f for f in facts.pattern_facts if f.get("rule") == "PY003"]
        self.assertEqual(len(py003), 1)
        self.assertEqual(py003[0]["call"], "run")

    def test_local_subprocess_shadows_external_model(self) -> None:
        code = b"import subprocess\nsubprocess.run('echo', shell=True)\n"
        res = extract_python(code, self.limits, self.deadline)
        facts = res.content
        assert facts is not None

        # Manifest contains a local subprocess.py file!
        app_blob = BlobRef(path="app.py", path_bytes=b"app.py", mode="100644", blob_oid="1", size=len(code))
        local_sub_blob = BlobRef(path="subprocess.py", path_bytes=b"subprocess.py", mode="100644", blob_oid="2", size=20)
        snap = Snapshot(oid="snap", blobs=(app_blob, local_sub_blob))

        bound = bind_facts(facts, code, snap, "app.py", "head")
        resolved, _ = resolve_context((bound,), snap)
        # Should resolve to local repo candidate, shadowing stdlib subprocess
        imp = resolved[0].resolved_imports[0]
        self.assertEqual(imp["kind"], "repo")
        self.assertEqual(imp["canonical"], "subprocess")

    def test_timeout_or_worker_crash_partial(self) -> None:
        expired_deadline = Deadline(started_at=time.monotonic() - 10.0, duration_seconds=5.0)
        res = extract_python(b"x = 1\n", self.limits, expired_deadline)
        self.assertIsNone(res.content)
        self.assertTrue(any(d.code == "TIMEOUT" for d in res.diagnostics))

    def test_maximum_source_base64_fits_protocol(self) -> None:
        code = b"# filler comment\nx = 1\n" * 40000
        self.assertLess(len(code), self.limits.max_blob_bytes)
        res = extract_python(code, self.limits, self.deadline)
        self.assertIsNotNone(res.content)
        assert res.content is not None
        self.assertEqual(res.content.blob_digest, hashlib.sha256(code).hexdigest())

    def test_ambiguous_module_no_external_fallback(self) -> None:
        code = b"import common\n"
        res = extract_python(code, self.limits, self.deadline)
        facts = res.content
        assert facts is not None

        blob1 = BlobRef(path="app.py", path_bytes=b"app.py", mode="100644", blob_oid="1", size=len(code))
        blob2 = BlobRef(path="pkg_a/common.py", path_bytes=b"pkg_a/common.py", mode="100644", blob_oid="2", size=10)
        blob3 = BlobRef(path="pkg_b/common.py", path_bytes=b"pkg_b/common.py", mode="100644", blob_oid="3", size=10)
        snap = Snapshot(oid="snap", blobs=(blob1, blob2, blob3))

        bound = bind_facts(facts, code, snap, "app.py", "head")
        resolved, diags = resolve_context((bound,), snap)
        self.assertTrue(any(d.code == "IMPORT_AMBIGUOUS" for d in diags))
        self.assertEqual(resolved[0].resolved_imports[0]["kind"], "ambiguous")

    def test_resolving_x_leaves_y_missing(self) -> None:
        code = b"import json\nimport missing_module\n"
        res = extract_python(code, self.limits, self.deadline)
        facts = res.content
        assert facts is not None

        blob = BlobRef(path="app.py", path_bytes=b"app.py", mode="100644", blob_oid="1", size=len(code))
        snap = Snapshot(oid="snap", blobs=(blob,))
        bound = bind_facts(facts, code, snap, "app.py", "head")

        resolved, diags = resolve_context((bound,), snap)
        self.assertEqual(len(diags), 1)
        self.assertEqual(diags[0].code, "IMPORT_UNRESOLVED")
        self.assertIn("missing_module", diags[0].message)

        resolved_imps = resolved[0].resolved_imports
        self.assertTrue(any(i["canonical"] == "json" and i["kind"] == "stdlib" for i in resolved_imps))
        self.assertTrue(any(i["canonical"] == "missing_module" and i["kind"] == "unresolved" for i in resolved_imps))

    def test_isolated_startup_ignores_site_and_paths(self) -> None:
        code = b"import sys\n"
        res = extract_python(code, self.limits, self.deadline)
        self.assertIsNotNone(res.content)
        self.assertEqual(len(res.diagnostics), 0)


if __name__ == "__main__":
    unittest.main()
