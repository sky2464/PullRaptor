"""Tests for PullRaptor orchestration kernel."""

import time
import unittest

from pullraptor.kernel import review
from pullraptor.models import FullReport, canonical_bytes
from tests.helpers import make_repo


class TestKernel(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = make_repo({
            "app.py": b"def main():\n    pass\n",
            ".pullraptor.toml": b"profile = 'structural'\n",
        })

    def tearDown(self) -> None:
        self.repo.cleanup()

    def test_review_structural_python_complete(self) -> None:
        base_c = self.repo.commit_ids[0]
        head_c = self.repo.commit({"app.py": b"def main():\n    print('hello')\n"})

        report, deadline, record_limits = review(
            self.repo.root, base_c, head_c, exact_base=True, use_cache=False
        )
        self.assertEqual(report.kind, "full")
        assert isinstance(report, FullReport)
        self.assertTrue(report.contract.discovery_complete)
        self.assertEqual(len(report.findings), 0)

    def test_review_with_finding(self) -> None:
        base_c = self.repo.commit_ids[0]
        head_c = self.repo.commit({"app.py": b"def main(cache=[]):\n    cache.append(1)\n"})

        report, deadline, record_limits = review(
            self.repo.root, base_c, head_c, exact_base=True, use_cache=False
        )
        self.assertEqual(report.kind, "full")
        assert isinstance(report, FullReport)
        self.assertEqual(len(report.findings), 1)
        self.assertEqual(report.findings[0].rule, "PY001")
        self.assertEqual(report.findings[0].delta, "newly_detected")

    def test_review_clean_and_incremental_identical(self) -> None:
        base_c = self.repo.commit_ids[0]
        head_c = self.repo.commit({"app.py": b"def main(cache=[]):\n    cache.append(1)\n"})

        # Run 1: clean (no cache)
        report1, d1, lim1 = review(self.repo.root, base_c, head_c, exact_base=True, use_cache=False)
        bytes1 = canonical_bytes(report1, limits=lim1, deadline=d1)

        # Run 2: incremental (cache enabled)
        report2, d2, lim2 = review(self.repo.root, base_c, head_c, exact_base=True, use_cache=True)
        bytes2 = canonical_bytes(report2, limits=lim2, deadline=d2)

        # Invariant: canonical bytes must be identical
        self.assertEqual(bytes1, bytes2)

    def test_review_diff_profile(self) -> None:
        base_c = self.repo.commit_ids[0]
        head_c = self.repo.commit({"app.py": b"def main(cache=[]):\n    cache.append(1)\n"})

        report, deadline, record_limits = review(
            self.repo.root, base_c, head_c, overrides={"profile": "diff"}, exact_base=True, use_cache=False
        )
        self.assertEqual(report.kind, "full")
        assert isinstance(report, FullReport)
        self.assertEqual(report.contract.profile, "diff")
        # diff profile evaluates no semantic AST rules
        self.assertEqual(len(report.findings), 0)

    def test_unresolved_import_incomplete_exit2(self) -> None:
        base_c = self.repo.commit_ids[0]
        head_c = self.repo.commit({"app.py": b"import nonexistent_package_xyz\n"})

        report, deadline, record_limits = review(
            self.repo.root, base_c, head_c, exact_base=True, use_cache=False
        )
        self.assertEqual(report.kind, "full")
        assert isinstance(report, FullReport)
        # An unresolved import produces an incomplete coverage receipt
        self.assertTrue(any(r.status == "incomplete" for r in report.receipts))


if __name__ == "__main__":
    unittest.main()
