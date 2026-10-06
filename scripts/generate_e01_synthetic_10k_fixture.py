#!/usr/bin/env python3.12
"""Generate the master-plan synthetic benchmark git fixture (development verification only).

Creates a disposable repository with:
- 10,000 tracked entries
- ~128 MiB admitted inventory (mostly non-Python documentation/data)
- at most 200 Python source files on base
- a head commit changing at most 20 Python files / 2,000 lines
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TARGET_ENTRIES = 10_000
TARGET_BYTES = 134_217_728
MAX_PYTHON_FILES = 200
MAX_CHANGED_PYTHON = 20
MAX_CHANGED_LINES = 2_000


@dataclass(frozen=True)
class SyntheticFixture:
    root: Path
    base_ref: str
    head_ref: str
    entry_count: int
    byte_total: int

    def cleanup(self) -> None:
        if self.root.exists():
            shutil.rmtree(self.root, ignore_errors=True)


def _run(cmd: list[str], *, cwd: Path) -> None:
    subprocess.run(cmd, cwd=cwd, check=True, capture_output=True)


def _tree_entry_count(root: Path, ref: str) -> int:
    proc = subprocess.run(
        ["git", "-C", str(root), "ls-tree", "-r", "--name-only", ref],
        check=True,
        capture_output=True,
        text=True,
    )
    return len([line for line in proc.stdout.splitlines() if line.strip()])


def _tree_byte_total(root: Path, ref: str) -> int:
    proc = subprocess.run(
        ["git", "-C", str(root), "ls-tree", "-r", "-l", ref],
        check=True,
        capture_output=True,
        text=True,
    )
    total = 0
    for line in proc.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 4 and parts[3].isdigit():
            total += int(parts[3])
    return total


def generate_fixture(output_parent: Path | None = None) -> SyntheticFixture:
    parent = output_parent or Path(tempfile.mkdtemp(prefix="pullraptor-e01-10k-"))
    root = parent / "synthetic-10k-repo"
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)

    _run(["git", "init", "-b", "main"], cwd=root)
    _run(["git", "config", "user.name", "PullRaptor Benchmark"], cwd=root)
    _run(["git", "config", "user.email", "benchmark@example.com"], cwd=root)
    _run(["git", "config", "commit.gpgsign", "false"], cwd=root)

    py_dir = root / "py"
    py_dir.mkdir()
    for idx in range(MAX_PYTHON_FILES):
        rel = py_dir / f"mod_{idx:03d}.py"
        rel.write_text(f"VALUE = {idx}\n\ndef run() -> int:\n    return VALUE\n", encoding="utf-8")

    docs_dir = root / "docs" / "inventory"
    docs_dir.mkdir(parents=True)
    entries_so_far = MAX_PYTHON_FILES
    chunk_size = 16_384
    chunks_needed = max(0, (TARGET_BYTES // chunk_size) - 1)
    for chunk_idx in range(chunks_needed):
        if entries_so_far >= TARGET_ENTRIES - 1:
            break
        path = docs_dir / f"blob_{chunk_idx:05d}.bin"
        payload = hashlib.sha256(f"chunk-{chunk_idx}".encode()).digest() * (chunk_size // 32)
        path.write_bytes(payload[:chunk_size])
        entries_so_far += 1

    filler_dir = root / "meta"
    filler_dir.mkdir()
    while entries_so_far < TARGET_ENTRIES:
        path = filler_dir / f"entry_{entries_so_far:05d}.txt"
        path.write_text(f"entry={entries_so_far}\n", encoding="utf-8")
        entries_so_far += 1

    _run(["git", "add", "-A"], cwd=root)
    _run(["git", "commit", "-m", "base synthetic fixture"], cwd=root)
    base_ref = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()

    changed_lines = 0
    changed_files = 0
    for idx in range(MAX_CHANGED_PYTHON):
        if changed_files >= MAX_CHANGED_PYTHON or changed_lines >= MAX_CHANGED_LINES:
            break
        rel = py_dir / f"mod_{idx:03d}.py"
        lines = rel.read_text(encoding="utf-8").splitlines()
        extra = min(100, MAX_CHANGED_LINES - changed_lines)
        lines.extend(f"# change {line}\n" for line in range(extra))
        rel.write_text("\n".join(lines) + "\n", encoding="utf-8")
        changed_lines += extra
        changed_files += 1

    _run(["git", "add", "-A"], cwd=root)
    _run(["git", "commit", "-m", "head synthetic changes"], cwd=root)
    head_ref = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()

    entry_count = _tree_entry_count(root, head_ref)
    byte_total = _tree_byte_total(root, head_ref)
    return SyntheticFixture(
        root=root,
        base_ref=base_ref,
        head_ref=head_ref,
        entry_count=entry_count,
        byte_total=byte_total,
    )


def write_manifest(fixture: SyntheticFixture, manifest_path: Path) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "pullraptor-e01-synthetic-10k-fixture/1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generator": "scripts/generate_e01_synthetic_10k_fixture.py",
        "requirements": {
            "entries": TARGET_ENTRIES,
            "total_bytes": TARGET_BYTES,
            "python_source_files_max": MAX_PYTHON_FILES,
            "changed_python_files_max": MAX_CHANGED_PYTHON,
            "changed_lines_max": MAX_CHANGED_LINES,
        },
        "observed": {
            "entry_count": fixture.entry_count,
            "byte_total": fixture.byte_total,
            "base_ref": fixture.base_ref,
            "head_ref": fixture.head_ref,
        },
        "fixture_path": str(fixture.root),
        "status": "generated",
    }
    manifest_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate E01 synthetic 10k benchmark git fixture.")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=REPO_ROOT / "tests" / "fixtures" / "e01" / "benchmark" / "synthetic-fixture-manifest.json",
    )
    parser.add_argument(
        "--keep",
        type=Path,
        help="Directory to place the generated repository (default: temp dir; deleted unless --keep)",
    )
    args = parser.parse_args(argv)
    parent = args.keep
    fixture = generate_fixture(parent)
    write_manifest(fixture, args.manifest)
    print(json.dumps({"manifest": str(args.manifest), "fixture_root": str(fixture.root)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
