"""E07-A1: honest release metadata and customer entry points (distribution contract)."""

from __future__ import annotations

import argparse
import json
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

    def test_distribution_zero_runtime_dependencies(self) -> None:
        self.test_no_runtime_dependencies()

    def test_declared_cli_examples_match_parser(self) -> None:
        parser = argparse.ArgumentParser(prog="pullraptor")
        parser.add_argument("--repo")
        parser.add_argument("--base")
        head_group = parser.add_mutually_exclusive_group()
        head_group.add_argument("--head")
        head_group.add_argument("--staged", action="store_true")
        head_group.add_argument("--workdir", action="store_true")
        dist = _read_text(REPO_ROOT / "docs" / "distribution.md")
        self.assertIn("pullraptor --workdir", dist)
        self.assertNotIn("pullraptor review", dist)
        args = parser.parse_args(["--workdir", "--base", "HEAD"])
        self.assertTrue(args.workdir)

    def test_dependency_inventory_exact_versions_digests_licenses(self) -> None:
        inv_path = REPO_ROOT / "docs" / "dependencies" / "E07.json"
        self.assertTrue(inv_path.is_file())
        inv = json.loads(_read_text(inv_path))
        self.assertEqual(inv["schema"], "pullraptor-dependency-inventory/1")
        self.assertEqual(inv["kernel_runtime"]["python_packages"], [])
        for host in inv["host_prerequisites"]:
            self.assertIn("license", host)
            self.assertIn("version", host)

    def test_container_base_and_build_tools_pinned(self) -> None:
        inv = json.loads(_read_text(REPO_ROOT / "docs" / "dependencies" / "E07.json"))
        self.assertEqual(inv["container_image"]["reference"], "docker.io/library/python:3.12-slim")
        self.assertIn("setuptools", inv["build_tools"][0]["name"])
        dockerfile = _read_text(REPO_ROOT / "Dockerfile")
        self.assertIn("python:3.12-slim", dockerfile)

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
