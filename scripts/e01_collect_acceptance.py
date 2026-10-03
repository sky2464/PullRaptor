#!/usr/bin/env python3.12
"""Collect E01 Task 9 acceptance artifacts (inventory, unittest log, module inventory)."""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ARTIFACTS = REPO / "docs" / "acceptance" / "artifacts" / "E01"


def _git_revision() -> str:
    out = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO,
        check=True,
        capture_output=True,
        text=True,
    )
    return out.stdout.strip()


def _list_tests() -> list[dict[str, str]]:
    tests_dir = REPO / "tests"
    entries: list[dict[str, str]] = []
    for path in sorted(tests_dir.glob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(item, ast.FunctionDef) and item.name.startswith("test_"):
                        entries.append(
                            {
                                "module": path.stem,
                                "class": node.name,
                                "test": item.name,
                            }
                        )
    return entries


def _module_inventory() -> dict[str, object]:
    src = REPO / "src" / "pullraptor"
    modules = sorted(p.name for p in src.glob("*.py"))
    line_count = sum(
        len(p.read_text(encoding="utf-8").splitlines()) for p in src.glob("*.py")
    )
    return {
        "production_modules": modules,
        "production_module_count": len(modules),
        "production_line_count": line_count,
        "runtime_dependencies": [],
        "python_baseline": "3.12.x",
    }


def main() -> int:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    revision = _git_revision()
    (ARTIFACTS / "git_revision.txt").write_text(revision + "\n", encoding="utf-8")

    inventory = {
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "revision": revision,
        "tests": _list_tests(),
        "test_count": len(_list_tests()),
        "inventory": _module_inventory(),
    }
    (ARTIFACTS / "test_inventory.json").write_text(
        json.dumps(inventory, indent=2) + "\n", encoding="utf-8"
    )

    log_path = ARTIFACTS / "unittest_discover_verbose.log"
    proc = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
        cwd=REPO,
        env={**os.environ, "PYTHONPATH": str(REPO / "src")},
        capture_output=True,
        text=True,
    )
    log_path.write_text(proc.stdout + proc.stderr, encoding="utf-8")
    (ARTIFACTS / "unittest_exit_code.txt").write_text(str(proc.returncode) + "\n")
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
