#!/usr/bin/env python3.12
"""Build E01 Task 9 requirement-assertion-fixture map (static; no test execution)."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ARTIFACTS = REPO / "docs" / "acceptance" / "artifacts" / "E01"
STATIC_INVENTORY = ARTIFACTS / "2026-10-03-static-inventory.json"
CACHE_MAP = ARTIFACTS / "2026-10-03-cache-output-assertion-map.md"
OVERLAY = ARTIFACTS / "task7-task8-assertion-overlay.json"
OUTPUT = ARTIFACTS / "requirement-assertion-fixture-map.json"

TASK_ACCEPTANCE: dict[int, list[str]] = {
    1: ["E01-A1"],
    2: ["E01-A1"],
    3: ["E01-A1"],
    4: ["E01-A1"],
    5: ["E01-A1", "E01-A2"],
    6: ["E01-A1"],
    7: ["E01-A1", "E01-A2"],
    8: ["E01-A1", "E01-A2"],
}

EVALUATION_INVARIANTS: list[dict[str, object]] = [
    {"id": "EVAL.immutable_comparison", "label": "Immutable comparison", "acceptance_ids": ["E01-A1"]},
    {"id": "EVAL.safe_ingestion", "label": "Safe ingestion", "acceptance_ids": ["E01-A1"]},
    {"id": "EVAL.location_fidelity", "label": "Location fidelity", "acceptance_ids": ["E01-A1"]},
    {"id": "EVAL.scope_honesty", "label": "Scope honesty", "acceptance_ids": ["E01-A1"]},
    {"id": "EVAL.differential_reporting", "label": "Differential reporting", "acceptance_ids": ["E01-A1"]},
    {"id": "EVAL.cache_correctness", "label": "Cache correctness", "acceptance_ids": ["E01-A2"]},
    {"id": "EVAL.pattern_restraint", "label": "Pattern restraint", "acceptance_ids": ["E01-A2"]},
    {"id": "EVAL.offline_behavior", "label": "Offline behavior", "acceptance_ids": ["E01-A1"]},
    {"id": "EVAL.resource_limits", "label": "Resource limits", "acceptance_ids": ["E01-A1"]},
    {"id": "EVAL.independent_scope", "label": "Independent scope", "acceptance_ids": ["E01-A1"]},
    {"id": "EVAL.strict_records", "label": "Strict records", "acceptance_ids": ["E01-A1"]},
    {"id": "EVAL.cache_admission", "label": "Cache admission", "acceptance_ids": ["E01-A1"]},
    {"id": "EVAL.process_authority", "label": "Process authority", "acceptance_ids": ["E01-A1"]},
    {"id": "EVAL.safe_presentation", "label": "Safe presentation", "acceptance_ids": ["E01-A1"]},
    {"id": "EVAL.recovery_guidance", "label": "Recovery guidance", "acceptance_ids": ["E01-A1"]},
    {"id": "EVAL.external_import_scope", "label": "External/import scope", "acceptance_ids": ["E01-A1"]},
    {"id": "EVAL.failure_output", "label": "Failure output", "acceptance_ids": ["E01-A1"]},
]


def _git_head() -> str:
    out = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO,
        check=True,
        capture_output=True,
        text=True,
    )
    return out.stdout.strip()


def _declaration_status(declarations: list[dict[str, object]]) -> str:
    if not declarations:
        return "unmapped_declaration"
    return "declaration_located"


def _merge_task78(
    task: int,
    planned_test: str,
    overlay: dict[str, object],
) -> dict[str, object] | None:
    bucket = overlay.get(f"named_task{task}")
    if not isinstance(bucket, dict):
        return None
    entry = bucket.get(planned_test)
    return entry if isinstance(entry, dict) else None


def build() -> dict[str, object]:
    static = json.loads(STATIC_INVENTORY.read_text(encoding="utf-8"))
    overlay = json.loads(OVERLAY.read_text(encoding="utf-8"))
    mapping_revision = static["source_revision"]
    head = _git_head()

    named_rows: list[dict[str, object]] = []
    coverage_counts = {"mapped": 0, "partial": 0, "unmapped": 0, "declaration_only": 0}

    for item in static["named_plan_inventory"]:
        task = int(item["task"])
        planned = str(item["planned_test"])
        declarations = item.get("declarations") or []
        detail = _merge_task78(task, planned, overlay)

        if detail:
            coverage = str(detail.get("coverage", "partial"))
            row = {
                "requirement_id": f"T{task}.{planned}",
                "task": task,
                "planned_test": planned,
                "acceptance_ids": TASK_ACCEPTANCE.get(task, ["E01-A1"]),
                "declaration_status": _declaration_status(declarations),
                "declarations": declarations,
                "mapping_kind": detail.get("mapping_kind", "partial"),
                "assertion_coverage": coverage,
                "primary_assertions": detail.get("assertions", []),
                "alternate_assertions": detail.get("alternates", []),
                "remaining_gap": detail.get("gap", ""),
                "runtime_result": "not_run",
                "expected_result": "not_run",
            }
        else:
            decl_status = _declaration_status(declarations)
            if decl_status == "declaration_located":
                coverage = "declaration_only"
                mapping_kind = "body_review_pending"
            else:
                coverage = "unmapped"
                mapping_kind = "unmapped_declaration"
            row = {
                "requirement_id": f"T{task}.{planned}",
                "task": task,
                "planned_test": planned,
                "acceptance_ids": TASK_ACCEPTANCE.get(task, ["E01-A1"]),
                "declaration_status": decl_status,
                "declarations": declarations,
                "mapping_kind": mapping_kind,
                "assertion_coverage": coverage,
                "primary_assertions": [],
                "alternate_assertions": [],
                "remaining_gap": "Task 1-6 assertion body review pending; see static inventory declarations",
                "runtime_result": "not_run",
                "expected_result": "not_run",
            }

        cov = row["assertion_coverage"]
        if cov in coverage_counts:
            coverage_counts[str(cov)] += 1
        elif cov == "declaration_only":
            coverage_counts["declaration_only"] += 1
        else:
            coverage_counts["partial"] += 1
        named_rows.append(row)

    unnamed_rows: list[dict[str, object]] = []
    for item in overlay.get("unnamed", []):
        if not isinstance(item, dict):
            continue
        unnamed_rows.append(
            {
                "requirement_id": str(item["id"]),
                "acceptance_ids": item.get("acceptance_ids", []),
                "proposed_fixture": item.get("proposed_fixture", ""),
                "assertion_coverage": item.get("coverage", "unmapped"),
                "source_artifact": CACHE_MAP.name,
                "runtime_result": "not_run",
                "expected_result": "not_run",
            }
        )

    eval_rows: list[dict[str, object]] = []
    for inv in EVALUATION_INVARIANTS:
        eval_rows.append(
            {
                "requirement_id": inv["id"],
                "label": inv["label"],
                "acceptance_ids": inv["acceptance_ids"],
                "assertion_coverage": "inventory_pending",
                "source": "docs/evaluation.md E01 required invariants",
                "runtime_result": "not_run",
                "expected_result": "not_run",
            }
        )

    partial_or_unmapped = sum(
        1
        for r in named_rows
        if r["assertion_coverage"] in {"partial", "unmapped", "declaration_only"}
    ) + sum(1 for r in unnamed_rows if r["assertion_coverage"] != "mapped")

    document = {
        "kind": "requirement_assertion_fixture_map",
        "date": datetime.now(timezone.utc).date().isoformat(),
        "producer_card": "E01-T9-MAP",
        "document_revision": head,
        "mapping_source_revision": mapping_revision,
        "trusted_base_revision": static.get("trusted_base_revision", mapping_revision),
        "method": "Merge static declaration inventory, cache/output assertion map overlay, and evaluation invariants; no imports or suite execution.",
        "input_artifacts": [
            str(STATIC_INVENTORY.relative_to(REPO)),
            str(CACHE_MAP.relative_to(REPO)),
            str(OVERLAY.relative_to(REPO)),
            "docs/evaluation.md",
        ],
        "acceptance_criteria": {
            "E01-A1": "not_run",
            "E01-A2": "not_run",
            "E01-A3": "not_run",
            "independent_decision": "pending",
        },
        "summary": {
            "named_plan_tests": len(named_rows),
            "named_declaration_located": sum(
                1 for r in named_rows if r["declaration_status"] == "declaration_located"
            ),
            "named_assertion_gaps": partial_or_unmapped,
            "unnamed_cache_output_obligations": len(unnamed_rows),
            "evaluation_invariant_rows": len(eval_rows),
            "task7_named_partial_or_unmapped": sum(
                1
                for r in named_rows
                if r["task"] == 7 and r["assertion_coverage"] != "mapped"
            ),
            "task8_named_partial_or_unmapped": sum(
                1
                for r in named_rows
                if r["task"] == 8 and r["assertion_coverage"] != "mapped"
            ),
            "coverage_bucket_counts": coverage_counts,
        },
        "named_requirements": named_rows,
        "unnamed_requirements": unnamed_rows,
        "evaluation_invariants": eval_rows,
        "downstream_cards": [
            "E01-T9-CACHE",
            "E01-T9-OUTPUT",
            "E01-T9-RECORDS",
            "E01-T9-CORPUS",
            "E01-T9-BENCH",
        ],
        "claim_limit": "Rows locate declarations and static gaps only. They do not pass criteria or authorize merge.",
    }
    return document


def main() -> int:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    payload = build()
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT} ({payload['summary']['named_plan_tests']} named rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
