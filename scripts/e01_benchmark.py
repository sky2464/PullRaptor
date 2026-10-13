#!/usr/bin/env python3.12
"""E01 benchmark measurements (development verification; not independent acceptance)."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import resource
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT_DIR = REPO / "docs" / "acceptance" / "artifacts" / "E01" / "benchmark"
MANIFEST = REPO / "tests" / "fixtures" / "e01" / "benchmark" / "manifest.json"
GENERATOR = REPO / "scripts" / "generate_e01_synthetic_10k_fixture.py"
REPETITIONS = 30

sys.path.insert(0, str(REPO / "src"))

from pullraptor.kernel import review  # noqa: E402
from pullraptor.models import FullReport, canonical_bytes  # noqa: E402


def _revision() -> str:
    return subprocess.check_output(["git", "-C", str(REPO), "rev-parse", "HEAD"], text=True).strip()


def _peak_rss_bytes() -> int:
    usage = resource.getrusage(resource.RUSAGE_SELF)
    rss = usage.ru_maxrss
    if sys.platform == "darwin":
        return int(rss)
    return int(rss) * 1024


def _p95(samples: list[float]) -> float:
    ordered = sorted(samples)
    idx = max(0, math.ceil(0.95 * len(ordered)) - 1)
    return ordered[idx]


def _ensure_fixture() -> dict:
    fixture_parent = REPO / "build" / "e01-synthetic-10k"
    fixture_parent.mkdir(parents=True, exist_ok=True)
    manifest_path = fixture_parent / "synthetic-fixture-manifest.json"
    proc = subprocess.run(
        [sys.executable, str(GENERATOR), "--keep", str(fixture_parent), "--manifest", str(manifest_path)],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return {"status": "failed", "cause": proc.stderr or proc.stdout}
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    observed = data.get("observed", {})
    root = Path(data.get("fixture_path", ""))
    try:
        manifest_rel = manifest_path.relative_to(REPO)
    except ValueError:
        manifest_rel = manifest_path
    try:
        root_rel = root.relative_to(REPO)
    except ValueError:
        root_rel = root
    return {
        "status": "generated",
        "manifest": str(manifest_rel),
        "fixture_root": str(root_rel),
        "base_ref": observed.get("base_ref"),
        "head_ref": observed.get("head_ref"),
        "entry_count": observed.get("entry_count"),
        "byte_total": observed.get("byte_total"),
    }


def _review_once(repo: Path, base_ref: str, head_ref: str, *, warm: bool) -> tuple[float, int]:
    resource.getrusage(resource.RUSAGE_SELF)  # baseline
    start = time.perf_counter()
    report, deadline, limits = review(
        repo=repo,
        base_ref=base_ref,
        head_ref=head_ref,
        use_cache=warm,
        exact_base=True,
    )
    if not isinstance(report, FullReport) or report.execution.get("exit_code") not in (0, 1):
        raise ValueError("incomplete benchmark review cannot be measured as success")
    canonical_bytes(report, limits=limits, deadline=deadline)
    elapsed = time.perf_counter() - start
    return elapsed, _peak_rss_bytes()


def _timed_series(repo: Path, base_ref: str, head_ref: str) -> dict:
    cold: list[float] = []
    warm: list[float] = []
    peak_rss = 0
    for _ in range(REPETITIONS):
        elapsed, rss = _review_once(repo, base_ref, head_ref, warm=False)
        cold.append(elapsed)
        peak_rss = max(peak_rss, rss)
    for _ in range(REPETITIONS):
        elapsed, rss = _review_once(repo, base_ref, head_ref, warm=True)
        warm.append(elapsed)
        peak_rss = max(peak_rss, rss)
    budgets = json.loads(MANIFEST.read_text(encoding="utf-8")).get("budgets", {})
    cold_p95 = _p95(cold)
    warm_p95 = _p95(warm)
    return {
        "repetitions": REPETITIONS,
        "cold_p95_seconds": cold_p95,
        "warm_p95_seconds": warm_p95,
        "peak_rss_bytes": peak_rss,
        "budgets": budgets,
        "within_budget": {
            "cold_p95": cold_p95 <= float(budgets.get("cold_p95_seconds_max", 30)),
            "warm_p95": warm_p95 <= float(budgets.get("warm_p95_seconds_max", 5)),
            "peak_rss": peak_rss <= int(budgets.get("peak_rss_bytes_max", 536870912)),
        },
        "cold_samples": cold,
        "warm_samples": warm,
    }


def _real_repository_pair() -> dict:
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pullraptor",
            "--repo",
            str(REPO),
            "--base",
            "HEAD~1",
            "--head",
            "HEAD",
            "--exact-base",
            "--format",
            "json",
        ],
        cwd=REPO,
        env={**dict(**{k: v for k, v in __import__("os").environ.items()}), "PYTHONPATH": f"{REPO / 'src'}"},
        capture_output=True,
        text=True,
    )
    return {
        "repository": "pullraptor-self",
        "base": "HEAD~1",
        "head": "HEAD",
        "exit_code": proc.returncode,
        "completed": proc.returncode in {0, 1},
        "stderr_tail": proc.stderr[-500:] if proc.stderr else "",
    }


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fixture = _ensure_fixture()
    measurements = {"status": "not_run", "cause": "fixture_generation_failed"}
    if fixture.get("status") == "generated":
        repo = Path(fixture["fixture_root"])
        measurements = _timed_series(repo, fixture["base_ref"], fixture["head_ref"])
        measurements["fixture"] = {
            "entry_count": fixture.get("entry_count"),
            "byte_total": fixture.get("byte_total"),
        }

    real = _real_repository_pair()
    receipt = {
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "source_revision": _revision(),
        "fixture_class": "synthetic_10k_master_plan",
        "synthetic_10k": {
            "fixture": fixture,
            "measurements": measurements,
        },
        "real_repositories": {"pairs": [real], "status": "development_measured"},
        "runner_spec": {
            "platform": sys.platform,
            "python": sys.version.split()[0],
            "note": "Local development host; 2-vCPU/4-GiB Linux is the acceptance target profile.",
        },
    }
    (OUT_DIR / "synthetic-10k-measurements.json").write_text(
        json.dumps(receipt, indent=2) + "\n",
        encoding="utf-8",
    )
    (OUT_DIR / "real-repositories.json").write_text(
        json.dumps({"status": "development_measured", "pairs": [real]}, indent=2) + "\n",
        encoding="utf-8",
    )
    index = json.loads((REPO / "docs" / "acceptance" / "artifacts" / "E01" / "benchmark" / "index.json").read_text())
    index["synthetic_10k_fixture"] = "measured_development" if fixture.get("status") == "generated" else "not_run"
    index["evidence_status"] = "partial"
    index["measurements"] = "docs/acceptance/artifacts/E01/benchmark/synthetic-10k-measurements.json"
    (REPO / "docs" / "acceptance" / "artifacts" / "E01" / "benchmark" / "index.json").write_text(
        json.dumps(index, indent=2) + "\n",
        encoding="utf-8",
    )
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest["synthetic_10k_fixture"]["status"] = (
        "development_measured" if fixture.get("status") == "generated" else "not_run"
    )
    manifest["synthetic_10k_fixture"]["generator"] = "scripts/generate_e01_synthetic_10k_fixture.py"
    manifest["runner_spec"]["status"] = "development_measured"
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(OUT_DIR / "synthetic-10k-measurements.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
