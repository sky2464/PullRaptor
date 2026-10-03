"""Static checks for the hardened GitHub review template (E02-A4)."""

from __future__ import annotations

from pathlib import Path
import re
import unittest

TEMPLATE = Path(__file__).resolve().parents[1] / "integrations" / "github" / "review.yml"
FULL_SHA_ACTION = re.compile(r"uses:\s+\S+@[0-9a-f]{40}")


class TestCiTemplate(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = TEMPLATE.read_text(encoding="utf-8")

    def test_actions_full_digest_pinned(self) -> None:
        uses_lines = [line for line in self.text.splitlines() if line.strip().startswith("uses:")]
        self.assertGreaterEqual(len(uses_lines), 2)
        for line in uses_lines:
            self.assertRegex(line, FULL_SHA_ACTION)

    def test_checkout_credentials_not_persisted(self) -> None:
        self.assertIn("persist-credentials: false", self.text)

    def test_pr_text_only_env_data(self) -> None:
        self.assertIn("PULLRAPTOR_PR_TITLE", self.text)
        self.assertIn("github.event.pull_request.title", self.text)
        self.assertNotRegex(self.text, r"run:.*\$\{\{.*github\.event\.pull_request\.title")

    def test_publisher_no_head_checkout_or_cache(self) -> None:
        publish_block = self.text.split("  publish:")[1]
        self.assertNotIn("actions/checkout", publish_block)
        self.assertNotIn("actions/cache", publish_block)

    def test_missing_isolation_refuses_hostile_profile(self) -> None:
        admission = "unavailable"
        analyze_block = self.text.split("  analyze:")[1].split("  publish:")[0]
        publisher_secret_seen_by_analysis = "PULLRAPTOR_PUBLISH_TOKEN" in analyze_block
        self.assertEqual(admission, "unavailable")
        self.assertFalse(publisher_secret_seen_by_analysis)


if __name__ == "__main__":
    unittest.main()
