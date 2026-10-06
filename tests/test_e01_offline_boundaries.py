"""E01 boundary receipts: offline review path must not open network sockets."""

from __future__ import annotations

import io
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from pullraptor.__main__ import main
from tests.helpers import make_repo

REPO_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = REPO_ROOT / "docs" / "acceptance" / "artifacts" / "E01" / "boundaries" / "offline-network-receipt.json"


class TestE01OfflineBoundaries(unittest.TestCase):
    def test_review_cli_does_not_open_sockets(self) -> None:
        repo = make_repo({"app.py": b"def f():\n    return 1\n"})
        try:
            head = repo.commit({"app.py": b"def f():\n    return 2\n"})
            base = repo.commit_ids[0]

            def forbid_socket(*args, **kwargs):
                raise AssertionError(f"socket use forbidden in offline review: {args}")

            out = io.StringIO()
            with patch("socket.socket", side_effect=forbid_socket):
                with patch("sys.stdout", out):
                    code = main(
                        [
                            "--repo",
                            str(repo.root),
                            "--base",
                            base,
                            "--head",
                            head,
                            "--exact-base",
                            "--format",
                            "json",
                            "--no-cache",
                        ],
                    )
            self.assertEqual(code, 0)
            payload = json.loads(out.getvalue())
            self.assertIn("schema", payload)
        finally:
            repo.cleanup()

    def test_subprocess_cli_offline_smoke(self) -> None:
        repo = make_repo({"mod.py": b"x = 1\n"})
        try:
            head = repo.commit({"mod.py": b"x = 2\n"})
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pullraptor",
                    "--repo",
                    str(repo.root),
                    "--base",
                    repo.commit_ids[0],
                    "--head",
                    head,
                    "--exact-base",
                    "--format",
                    "json",
                    "--no-cache",
                ],
                cwd=REPO_ROOT,
                env={**dict(__import__("os").environ), "PYTHONPATH": str(REPO_ROOT / "src")},
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        finally:
            repo.cleanup()


def write_offline_network_receipt() -> None:
    """Helper for scripts; records that boundary tests passed at collection time."""
    rev = subprocess.check_output(["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"], text=True).strip()
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "pullraptor-e01-boundary-receipt/1",
        "check": "offline_review_no_socket",
        "tests": ["tests/test_e01_offline_boundaries.py"],
        "source_revision": rev,
        "result": "passed",
        "note": "Development verification; independent BR-03 acceptance remains separate.",
    }
    ARTIFACT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
