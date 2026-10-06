#!/usr/bin/env python3
"""Generate docs/releases/beta-0.1-evidence-index.json from static maps (BR-02 helper)."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def main() -> int:
    rev = subprocess.check_output(["git", "-C", str(REPO), "rev-parse", "HEAD"], text=True).strip()
    map_path = REPO / "docs/acceptance/artifacts/E01/requirement-assertion-fixture-map.json"
    mapping = json.loads(map_path.read_text(encoding="utf-8"))
    summary = mapping.get("summary", {})
    out = {
        "schema": "pullraptor-beta-evidence-index/1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generator": "scripts/generate_beta_evidence_index.py",
        "candidate_source_revision": rev,
        "trusted_base_revision": "8c2622e060b59f93c3482afec96bc472c5de3ac2",
        "prior_map_revision": mapping.get("document_revision"),
        "mapping_source_revision": mapping.get("mapping_source_revision"),
        "beta_scope": "docs/releases/beta-0.1-scope.json",
        "release_tasks": "docs/release-tasks.json",
        "e01_assertion_map_summary": summary,
        "obligation_buckets": {
            "named_plan_tests": summary.get("named_plan_tests", 0),
            "named_assertion_gaps": summary.get("named_assertion_gaps", 0),
            "unnamed_cache_output_obligations": summary.get("unnamed_cache_output_obligations", 0),
            "evaluation_invariant_rows": summary.get("evaluation_invariant_rows", 0)
        },
        "stale_evidence_policy": "Historical artifacts before candidate_source_revision remain retained but marked stale unless re-run.",
        "uncommitted_local_preparation": "E04/E05/E06/E11 stubs in working tree excluded from release candidate per dispatch baseline.",
        "beta_release_queue": [
            {"id": "BR-01", "status": "partial", "note": "scope artifacts produced; maintainer approval pending"},
            {"id": "BR-02", "status": "partial", "note": "index generated; full assertion body reconciliation ongoing"},
            {"id": "BR-03", "status": "partial", "note": "development tests; artifact placeholders updated after suite run"},
            {"id": "BR-04", "status": "partial", "note": "tests.test_cache/test_kernel"},
            {"id": "BR-05", "status": "partial", "note": "tests.test_rules corpus in tests; pinned fixture dir manifest added"},
            {"id": "BR-06", "status": "partial", "note": "synthetic 10k generator and scripts/e01_benchmark.py; measurements in docs/acceptance/artifacts/E01/benchmark/"},
            {"id": "BR-07", "status": "blocked", "note": "independent reviewer unassigned"},
            {"id": "BR-08", "status": "partial", "note": "entrypoint containment + CI smoke script"},
            {"id": "BR-09", "status": "partial", "note": "git archive wheel builds; rebuild at commit OID before publication"},
            {"id": "BR-10", "status": "partial", "note": "CI linux venv smoke + macOS development_verified; independent acceptance pending"},
            {"id": "BR-11", "status": "partial", "note": "draft customer docs"},
            {"id": "BR-12", "status": "partial", "note": "PYTHONPATH=src python3.12 unittest discover log refreshed"},
            {"id": "BR-13", "status": "blocked", "note": "independent reviewer unassigned"},
            {"id": "BR-14", "status": "partial", "note": "readiness dossier draft; ready_for_release false"}
        ],
        "development_verification": {
            "command": "PYTHONPATH=src python3.12 -m unittest discover -s tests -v",
            "evidence_path": "docs/acceptance/artifacts/E01/unittest_discover_verbose.log",
            "status": "see_latest_log"
        },
    }
    dest = REPO / "docs/releases/beta-0.1-evidence-index.json"
    dest.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(dest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
