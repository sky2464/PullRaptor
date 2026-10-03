"""Tests for PullRaptor bounded subprocess execution."""

import os
from pathlib import Path
import sys
import time
import unittest

from pullraptor.models import Deadline, ProcessBounds
from pullraptor.process import run_bounded


class TestProcess(unittest.TestCase):
    def test_run_bounded_success(self) -> None:
        bounds = ProcessBounds(max_stdout_bytes=1024, max_stderr_bytes=1024, timeout_seconds=2.0)
        deadline = Deadline(started_at=time.monotonic(), duration_seconds=10.0)
        res = run_bounded(
            (sys.executable, "-c", "import sys; sys.stdout.write('hello'); sys.stderr.write('world')"),
            cwd=Path.cwd(),
            env={"PATH": os.environ.get("PATH", "")},
            deadline=deadline,
            bounds=bounds,
        )
        self.assertEqual(res.returncode, 0)
        self.assertEqual(res.stdout, b"hello")
        self.assertEqual(res.stderr, b"world")
        self.assertFalse(res.timed_out)
        self.assertFalse(res.stdout_truncated)

    def test_output_flood_stopped(self) -> None:
        bounds = ProcessBounds(max_stdout_bytes=50, max_stderr_bytes=1024, timeout_seconds=2.0)
        deadline = Deadline(started_at=time.monotonic(), duration_seconds=10.0)
        # Process attempts to write 100,000 bytes
        res = run_bounded(
            (sys.executable, "-c", "import sys; sys.stdout.write('A' * 100000); sys.stdout.flush()"),
            cwd=Path.cwd(),
            env={"PATH": os.environ.get("PATH", "")},
            deadline=deadline,
            bounds=bounds,
        )
        self.assertTrue(res.stdout_truncated)
        self.assertLessEqual(len(res.stdout), 50)

    def test_timeout_and_process_tree_cleanup(self) -> None:
        bounds = ProcessBounds(max_stdout_bytes=1024, max_stderr_bytes=1024, timeout_seconds=0.2)
        deadline = Deadline(started_at=time.monotonic(), duration_seconds=10.0)
        start = time.monotonic()
        res = run_bounded(
            (sys.executable, "-c", "import time; time.sleep(5)"),
            cwd=Path.cwd(),
            env={"PATH": os.environ.get("PATH", "")},
            deadline=deadline,
            bounds=bounds,
        )
        elapsed = time.monotonic() - start
        self.assertTrue(res.timed_out)
        self.assertLess(elapsed, 1.5)

    def test_shared_deadline_not_reset(self) -> None:
        # Deadline that has only 0.2s left
        start = time.monotonic() - 9.8
        deadline = Deadline(started_at=start, duration_seconds=10.0, reserve_seconds=0.1)
        bounds = ProcessBounds(max_stdout_bytes=1024, max_stderr_bytes=1024, timeout_seconds=5.0)
        res = run_bounded(
            (sys.executable, "-c", "import time; time.sleep(2)"),
            cwd=Path.cwd(),
            env={"PATH": os.environ.get("PATH", "")},
            deadline=deadline,
            bounds=bounds,
        )
        self.assertTrue(res.timed_out)

    def test_worker_environment_has_no_credentials(self) -> None:
        # Pass a sanitized env and assert secret tokens are not leaked
        env = {"PATH": os.environ.get("PATH", ""), "SAFE_VAR": "ok"}
        bounds = ProcessBounds(max_stdout_bytes=1024, max_stderr_bytes=1024, timeout_seconds=2.0)
        deadline = Deadline(started_at=time.monotonic(), duration_seconds=10.0)
        res = run_bounded(
            (sys.executable, "-c", "import os; print(os.environ.get('GITHUB_TOKEN', 'NONE'))"),
            cwd=Path.cwd(),
            env=env,
            deadline=deadline,
            bounds=bounds,
        )
        self.assertEqual(res.stdout.strip(), b"NONE")

    def test_stdin_input_requires_positive_cap(self) -> None:
        bounds = ProcessBounds(max_stdout_bytes=1024, max_stderr_bytes=1024, timeout_seconds=2.0)
        deadline = Deadline(started_at=time.monotonic(), duration_seconds=10.0)
        res = run_bounded(
            (sys.executable, "-c", "import sys; print(sys.stdin.read())"),
            cwd=Path.cwd(),
            env={"PATH": os.environ.get("PATH", "")},
            deadline=deadline,
            bounds=bounds,
            input_bytes=b"hello",
            max_input_bytes=0,
        )
        self.assertNotEqual(res.returncode, 0)
        self.assertIn(b"input cap", res.stderr)

    def test_stdin_input_delivered_and_closed(self) -> None:
        bounds = ProcessBounds(max_stdout_bytes=1024, max_stderr_bytes=1024, timeout_seconds=2.0)
        deadline = Deadline(started_at=time.monotonic(), duration_seconds=10.0)
        res = run_bounded(
            (sys.executable, "-c", "import sys; print(sys.stdin.read())"),
            cwd=Path.cwd(),
            env={"PATH": os.environ.get("PATH", "")},
            deadline=deadline,
            bounds=bounds,
            input_bytes=b"payload",
            max_input_bytes=64,
        )
        self.assertEqual(res.returncode, 0)
        self.assertEqual(res.stdout.strip(), b"payload")

    def test_stdin_over_cap_rejected_before_launch(self) -> None:
        bounds = ProcessBounds(max_stdout_bytes=1024, max_stderr_bytes=1024, timeout_seconds=2.0)
        deadline = Deadline(started_at=time.monotonic(), duration_seconds=10.0)
        res = run_bounded(
            (sys.executable, "-c", "print('unused')"),
            cwd=Path.cwd(),
            env={"PATH": os.environ.get("PATH", "")},
            deadline=deadline,
            bounds=bounds,
            input_bytes=b"x" * 100,
            max_input_bytes=10,
        )
        self.assertIn(b"input exceeds", res.stderr)


if __name__ == "__main__":
    unittest.main()
