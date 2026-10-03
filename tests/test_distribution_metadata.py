"""E07-A1: honest release metadata and customer entry points (distribution contract)."""

from __future__ import annotations

import tomllib
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class TestDistributionMetadata(unittest.TestCase):
    def test_python_minor_claim_matches_acceptance(self) -> None:
        pyproject = tomllib.loads(_read_text(REPO_ROOT / "pyproject.toml"))
        requires = pyproject["project"]["requires-python"]
        admitted_python_minors = ("3.12",)
        self.assertIn("3.12", requires)
        normalized = requires.replace(" ", "")
        self.assertIn("<3.13", normalized)
        self.assertNotRegex(normalized, r">=3\.1[3-9]|>=4\.|~=3\.1[3-9]")
        self.assertEqual(admitted_python_minors, ("3.12",))

    def test_no_runtime_dependencies(self) -> None:
        pyproject = tomllib.loads(_read_text(REPO_ROOT / "pyproject.toml"))
        deps = pyproject["project"].get("dependencies", [])
        self.assertEqual(deps, [])

    def test_image_cli_default(self) -> None:
        dockerfile = _read_text(REPO_ROOT / "Dockerfile")
        self.assertIn('CMD ["pullraptor", "--help"]', dockerfile)
        self.assertNotIn("unittest", dockerfile)

    def test_no_global_safe_directory_wildcard(self) -> None:
        dockerfile = _read_text(REPO_ROOT / "Dockerfile")
        self.assertNotIn("safe.directory '*'", dockerfile)
        self.assertNotIn('safe.directory="*"', dockerfile)
        kernel = _read_text(REPO_ROOT / "src" / "pullraptor" / "git_snapshot.py")
        self.assertNotIn("safe.directory=*", kernel)

    def test_customer_no_source_clone(self) -> None:
        dist_doc = REPO_ROOT / "docs" / "distribution.md"
        self.assertTrue(dist_doc.is_file(), "docs/distribution.md must document install without clone")
        text = _read_text(dist_doc)
        self.assertIn("pip install", text)
        self.assertIn("wheel", text.lower())


if __name__ == "__main__":
    unittest.main()
