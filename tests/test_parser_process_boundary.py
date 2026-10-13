"""Real own-source parser/process boundary regressions; source strings are data."""
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import unittest
from unittest.mock import patch

from pullraptor.models import Deadline, Limits
from pullraptor.python_facts import extract_python


class ParserBoundary(unittest.TestCase):
    def test_extraction_uses_neutral_isolated_worker(self):
        import pullraptor.process as process
        real = process.subprocess.Popen
        calls = []
        def observe(argv, **kwargs):
            calls.append((argv, kwargs))
            return real(argv, **kwargs)
        with patch.object(process.subprocess, "Popen", side_effect=observe), patch.dict(os.environ, {"GITHUB_TOKEN": "boundary-canary", "PYTHONPATH": "/untrusted"}):
            result = extract_python(b"def f(x=[]):\n    x.append(1)\n", Limits(), Deadline(time.monotonic(), 30))
        self.assertIsNotNone(result.content)
        self.assertEqual(len(calls), 1)
        argv, options = calls[0]
        self.assertEqual(tuple(argv[1:3]), ("-I", "-S"))
        self.assertNotIn("GITHUB_TOKEN", options["env"])
        self.assertNotIn("PYTHONPATH", options["env"])
        self.assertNotEqual(Path(options["cwd"]), Path.cwd())
        self.assertTrue(options["close_fds"])

    def test_blocked_stdin_obeys_deadline(self):
        # Outer watchdog bounds the historical bug without leaving descendants.
        program = """import os,sys,time
from pathlib import Path
from pullraptor.process import run_bounded
from pullraptor.models import Deadline,ProcessBounds
r=run_bounded((sys.executable,'-I','-S','-c','import time; time.sleep(10)'),cwd=Path('/tmp'),env={},deadline=Deadline(time.monotonic(),3,1),bounds=ProcessBounds(timeout_seconds=.15),input_bytes=b'x'*1000000,max_input_bytes=1000000)
assert r.timed_out and r.duration_seconds < 1
"""
        child = subprocess.Popen((sys.executable, "-c", program), env={"PATH": os.environ.get("PATH", ""), "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}, start_new_session=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            out, err = child.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            child.communicate()
            self.fail("stdin backpressure escaped subprocess deadline")
        self.assertEqual(child.returncode, 0, err.decode())
