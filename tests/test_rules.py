"""Tests for PullRaptor advisory rule pack (PY001, PY002, PY003)."""

from pathlib import Path
import time
import unittest

from pullraptor.models import (
    BlobRef,
    BoundFacts,
    Config,
    Deadline,
    Limits,
    Snapshot,
    Span,
)
from pullraptor.python_facts import bind_facts, extract_python, resolve_context
from pullraptor.rules import evaluate_rules


class TestRules(unittest.TestCase):
    def setUp(self) -> None:
        self.limits = Limits()
        self.deadline = Deadline(started_at=time.monotonic(), duration_seconds=30.0)
        self.config = Config()

    def _eval_source(self, code: bytes, filename: str = "test_file.py", extra_blobs: tuple[BlobRef, ...] = ()) -> tuple:
        res = extract_python(code, self.limits, self.deadline)
        facts = res.content
        assert facts is not None, f"Failed to extract facts: {res.diagnostics}"

        this_blob = BlobRef(path=filename, path_bytes=filename.encode("utf-8"), mode="100644", blob_oid="oid1", size=len(code))
        snap = Snapshot(oid="snap1", blobs=(this_blob,) + extra_blobs)
        bound = bind_facts(facts, code, snap, filename, "head")
        resolved, _ = resolve_context((bound,), snap)
        return evaluate_rules(resolved, snap, self.config)

    # --- Pinned tests ---

    def test_intentional_patterns_never_defect_claim(self) -> None:
        code = b"def f(cache={}):\n    cache['key'] = 1\n"
        findings = self._eval_source(code)
        self.assertEqual(len(findings), 1)
        f = findings[0]
        self.assertEqual(f.policy_class, "advisory")
        self.assertEqual(f.severity, "advisory")
        self.assertNotIn("bug", f.claim.lower())
        self.assertNotIn("defect", f.claim.lower())

    def test_shadowed_subprocess_no_shell_claim(self) -> None:
        code = b"""
class FakeSubprocess:
    def run(self, cmd, shell=False): pass

subprocess = FakeSubprocess()
subprocess.run("ls", shell=True)
"""
        findings = self._eval_source(code)
        py003 = [f for f in findings if f.rule == "PY003"]
        self.assertEqual(len(py003), 0)

    def test_conditional_reraise_not_classified_as_swallowed(self) -> None:
        code = b"""
try:
    do_work()
except:
    if condition:
        raise
"""
        findings = self._eval_source(code)
        py002 = [f for f in findings if f.rule == "PY002"]
        self.assertEqual(len(py002), 0)

    def test_untrusted_command_not_inferred_from_shell_true(self) -> None:
        code = b"import subprocess\nsubprocess.run('echo hello', shell=True)\n"
        findings = self._eval_source(code)
        py003 = [f for f in findings if f.rule == "PY003"]
        self.assertEqual(len(py003), 1)
        f = py003[0]
        self.assertNotIn("injection", f.claim.lower())
        self.assertNotIn("untrusted", f.claim.lower())
        self.assertNotIn("exploit", f.claim.lower())

    # --- 10 Positive & 10 Negative fixtures for PY001 ---

    def test_py001_positives(self) -> None:
        cases = [
            b"def f(x=[]): x.append(1)",
            b"def f(x=[]): x.extend([1])",
            b"def f(x=[]): x.insert(0, 1)",
            b"def f(x=[]): x.pop()",
            b"def f(x=[]): x.remove(1)",
            b"def f(x=[]): x.clear()",
            b"def f(x=[]): x[0] = 1",
            b"def f(d={}): d['a'] = 1",
            b"def f(d={}): d.update({'a': 1})",
            b"def f(s=set()): s.add(1)",
        ]
        for idx, code in enumerate(cases):
            with self.subTest(case=idx):
                findings = self._eval_source(code)
                py001 = [f for f in findings if f.rule == "PY001"]
                self.assertEqual(len(py001), 1, f"Failed on case {idx}: {code!r}")

    def test_py001_negatives(self) -> None:
        cases = [
            b"def f(x=None): pass",
            b"def f(x=1): pass",
            b"def f(x='str'): pass",
            b"def f(x=()): pass",  # tuple is immutable
            b"def f(x=[]): pass",  # default list, but no mutation
            b"def f(x=[]): y = x",  # alias, not direct mutation
            b"def f(x=[]):\n    x = list(x)\n    x.append(1)",  # reassigned
            b"def f(x=[]):\n    def inner(): x.append(1)",  # nested function
            b"def f(d={}): x = d['a']",  # read, not write
            b"def f(s=set()): pass",  # set default, no mutation
        ]
        for idx, code in enumerate(cases):
            with self.subTest(case=idx):
                findings = self._eval_source(code)
                py001 = [f for f in findings if f.rule == "PY001"]
                self.assertEqual(len(py001), 0, f"False positive on case {idx}: {code!r}")

    # --- 10 Positive & 10 Negative fixtures for PY002 ---

    def test_py002_positives(self) -> None:
        cases = [
            b"try:\n    pass\nexcept:\n    pass",
            b"try:\n    pass\nexcept:\n    return 1",
            b"try:\n    pass\nexcept:\n    x = 1",
            b"try:\n    pass\nexcept:\n    print('error')",
            b"try:\n    pass\nexcept:\n    pass\n    return",
            b"try:\n    pass\nexcept BaseException:\n    pass",
            b"try:\n    pass\nexcept BaseException:\n    return 0",
            b"try:\n    pass\nexcept BaseException:\n    log('err')",
            b"try:\n    x = 1\nexcept:\n    x = 0",
            b"try:\n    pass\nexcept:\n    do_fallback()\n    return None",
        ]
        for idx, code in enumerate(cases):
            with self.subTest(case=idx):
                findings = self._eval_source(code)
                py002 = [f for f in findings if f.rule == "PY002"]
                self.assertEqual(len(py002), 1, f"Failed on case {idx}: {code!r}")

    def test_py002_negatives(self) -> None:
        cases = [
            b"try:\n    pass\nexcept ValueError:\n    pass",  # specific exception
            b"try:\n    pass\nexcept Exception:\n    pass",  # Exception, not bare
            b"try:\n    pass\nexcept:\n    raise",  # re-raises
            b"try:\n    pass\nexcept:\n    if True: pass",  # branching
            b"try:\n    pass\nexcept:\n    for i in [1]: pass",  # loop
            b"try:\n    pass\nexcept:\n    while False: pass",  # loop
            b"try:\n    pass\nexcept:\n    try: pass\n    except ValueError: pass",  # nested try
            b"try:\n    pass\nexcept:\n    raise RuntimeError()",  # raises
            b"try:\n    pass\nexcept KeyError:\n    return None",
            b"try:\n    pass\nexcept (IOError, OSError):\n    pass",
        ]
        for idx, code in enumerate(cases):
            with self.subTest(case=idx):
                findings = self._eval_source(code)
                py002 = [f for f in findings if f.rule == "PY002"]
                self.assertEqual(len(py002), 0, f"False positive on case {idx}: {code!r}")

    # --- 10 Positive & 10 Negative fixtures for PY003 ---

    def test_py003_positives(self) -> None:
        cases = [
            b"import subprocess\nsubprocess.run('ls', shell=True)",
            b"import subprocess\nsubprocess.Popen('ls', shell=True)",
            b"import subprocess\nsubprocess.call('ls', shell=True)",
            b"import subprocess\nsubprocess.check_call('ls', shell=True)",
            b"import subprocess\nsubprocess.check_output('ls', shell=True)",
            b"import subprocess as sp\nsp.run('ls', shell=True)",
            b"import subprocess as sp\nsp.Popen('ls', shell=True)",
            b"from subprocess import run\nrun('ls', shell=True)",
            b"from subprocess import Popen\nPopen('ls', shell=True)",
            b"from subprocess import check_output\ncheck_output('ls', shell=True)",
        ]
        for idx, code in enumerate(cases):
            with self.subTest(case=idx):
                findings = self._eval_source(code)
                py003 = [f for f in findings if f.rule == "PY003"]
                self.assertEqual(len(py003), 1, f"Failed on case {idx}: {code!r}")

    def test_py003_negatives(self) -> None:
        cases = [
            b"import subprocess\nsubprocess.run('ls', shell=False)",
            b"import subprocess\nsubprocess.run('ls')",  # default shell=False
            b"import subprocess\nsubprocess.Popen(['ls'])",
            b"def run(cmd, shell=True): pass\nrun('ls', shell=True)",  # custom run function
            b"class Runner:\n    def run(self, shell=True): pass\nRunner().run(shell=True)",
            b"import os\nos.system('ls')",  # not subprocess
            b"import subprocess\nsubprocess.run('ls', shell=0)",  # int 0, not True
            b"import subprocess\nsubprocess.run('ls', shell=None)",
            b"import subprocess\nsh = True\nsubprocess.run('ls', shell=sh)",  # non-literal variable
            b"import subprocess\nsubprocess.list2cmdline(['ls'])",
        ]
        for idx, code in enumerate(cases):
            with self.subTest(case=idx):
                findings = self._eval_source(code)
                py003 = [f for f in findings if f.rule == "PY003"]
                self.assertEqual(len(py003), 0, f"False positive on case {idx}: {code!r}")


if __name__ == "__main__":
    unittest.main()
