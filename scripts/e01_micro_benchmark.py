#!/usr/bin/env python3.12
"""Record a small warm/cold timing sample; not a substitute for the master-plan 10k-file fixture."""

from __future__ import annotations

import json
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT))

from pullraptor.kernel import review  # noqa: E402
from tests.helpers import make_repo  # noqa: E402

OUT = REPO_ROOT / "docs" / "acceptance" / "artifacts" / "E01" / "micro_benchmark.json"
REPETITIONS = 30


def _one_run(warm: bool) -> float:
    fixture = make_repo(
        {
            "pkg/mod.py": b"def mutate(items=[]):\n    items.append(1)\n",
            "pkg/util.py": b"import subprocess\nsubprocess.run(['echo'], shell=True)\n",
        }
    )
    try:
        head = fixture.commit({"pkg/mod.py": b"def mutate(items=[]):\n    items.append(2)\n"})
        start = time.perf_counter()
        review(
            repo=fixture.root,
            base_ref="HEAD",
            head_ref=head,
            use_cache=warm,
        )
        return time.perf_counter() - start
    finally:
        fixture.cleanup()


def main() -> None:
    cold = [_one_run(False) for _ in range(REPETITIONS)]
    warm = [_one_run(True) for _ in range(REPETITIONS)]
    payload = {
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "fixture": "tests.helpers.make_repo two-file Python (not master-plan 10k-file corpus)",
        "repetitions": REPETITIONS,
        "cold_seconds": {
            "samples": cold,
            "p50": statistics.median(cold),
            "p95": sorted(cold)[int(0.95 * len(cold)) - 1],
        },
        "warm_seconds": {
            "samples": warm,
            "p50": statistics.median(warm),
            "p95": sorted(warm)[int(0.95 * len(warm)) - 1],
        },
        "rss_bytes": None,
        "master_plan_fixture_status": "not_run",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
