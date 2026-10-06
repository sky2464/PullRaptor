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
        "released_package_version": "0.1.0b1",
        "release_manifest": "docs/releases/beta-0.1-release-manifest.json",
        "beta_release_queue": [
            {"id": "BR-01", "status": "passed", "note": "see beta-0.1-decisions.md and manifest"},
            {"id": "BR-02", "status": "partial", "note": "index rebaselined at HEAD; full E01 assertion body reconciliation ongoing (E01-T9-MAP)"},
            {"id": "BR-03", "status": "passed", "note": "beta subset boundary tests and development suite"},
            {"id": "BR-04", "status": "passed", "note": "cache/kernel evidence for beta scope"},
            {"id": "BR-05", "status": "partial", "note": "rules corpus; full map reconciliation open"},
            {"id": "BR-06", "status": "passed", "note": "synthetic benchmark tooling and artifacts"},
            {"id": "BR-07", "status": "passed", "note": "independent E01 beta subset acceptance"},
            {"id": "BR-08", "status": "passed", "note": "entrypoint containment and CI smoke"},
            {"id": "BR-09", "status": "passed", "note": "git-archive wheels at tag OID"},
            {"id": "BR-10", "status": "passed", "note": "linux acceptance workflow and install evidence"},
            {"id": "BR-11", "status": "passed", "note": "customer docs and recovery rehearsal"},
            {"id": "BR-12", "status": "passed", "note": "candidate verification complete for b1"},
            {"id": "BR-13", "status": "passed", "note": "independent E07 beta subset acceptance"},
            {"id": "BR-14", "status": "passed", "note": "ready_for_release true in manifest"},
            {"id": "BR-15", "status": "passed", "note": "human publication authorization recorded"},
            {"id": "BR-16", "status": "passed", "note": "GitHub Release v0.1.0b1 published"},
            {"id": "BR-17", "status": "passed", "note": "download/install smoke verified"},
            {"id": "BR-18", "status": "pending", "note": "required before 0.1.0b2 update/rollback claims; see beta-0.1.0b2-entry-criteria.md"}
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
