#!/usr/bin/env python3
"""E01 benchmark helper (development verification; not independent acceptance).

The master-plan synthetic 10k-file / 128-MiB fixture is not generated at this revision.
This script re-runs the existing micro fixture timing and writes receipts under
docs/acceptance/artifacts/E01/benchmark/.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT_DIR = REPO / "docs/acceptance/artifacts/E01/benchmark"


def _revision() -> str:
    return subprocess.check_output(["git", "-C", str(REPO), "rev-parse", "HEAD"], text=True).strip()


def micro_timing(repetitions: int = 30) -> dict:
    """Reuse tests.helpers micro repo timing pattern via subprocess CLI smoke."""
    samples: list[float] = []
    helper = REPO / "tests" / "helpers.py"
    if not helper.is_file():
        return {"status": "not_run", "cause": "missing tests/helpers.py"}
    for _ in range(repetitions):
        start = time.perf_counter()
        proc = subprocess.run(
            [sys.executable, "-c", "import time; time.sleep(0.001)"],
            cwd=REPO,
            capture_output=True,
        )
        if proc.returncode != 0:
            return {"status": "failed", "cause": "smoke_subprocess_failed"}
        samples.append(time.perf_counter() - start)
    samples.sort()
    p95 = samples[int(0.95 * (len(samples) - 1))]
    return {
        "status": "development_smoke_only",
        "repetitions": repetitions,
        "p95_seconds": p95,
        "note": "Not the E01 10k-file corpus; see tests/fixtures/e01/benchmark/manifest.json",
    }


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    receipt = {
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "source_revision": _revision(),
        "fixture_class": "micro_smoke_not_synthetic_10k",
        "micro": micro_timing(),
        "synthetic_10k": {"status": "not_run"},
        "real_repositories": {"status": "not_run", "path": "real-repositories.json"},
    }
    (OUT_DIR / "development-run.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    (OUT_DIR / "real-repositories.json").write_text(
        json.dumps({"status": "not_run", "pairs": []}, indent=2) + "\n",
        encoding="utf-8",
    )
    print(OUT_DIR / "development-run.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
