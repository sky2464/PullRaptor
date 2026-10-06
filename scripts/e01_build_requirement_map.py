#!/usr/bin/env python3.12
"""Build E01 Task 9 requirement-assertion-fixture map (static; no test execution)."""

from __future__ import annotations

import argparse
import ast
import hashlib
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


def source_identity(root: Path = REPO) -> dict[str, object]:
    """Pin product bytes separately from test/evidence/document revisions."""
    files = {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
             for path in sorted((root / "src").rglob("*.py"))}
    digest = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
    return {"files": files, "sha256": digest}


def assertion_inventory(root: Path = REPO) -> list[dict[str, object]]:
    """Locate actual assertion expressions; this does not establish adequacy."""
    inventory = []
    for path in sorted((root / "tests").glob("test_*.py")):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for owner in tree.body:
            if not isinstance(owner, ast.ClassDef):
                continue
            for function in owner.body:
                if not isinstance(function, ast.FunctionDef) or not function.name.startswith("test_"):
                    continue
                assertions = []
                for node in ast.walk(function):
                    is_assert = isinstance(node, ast.Assert)
                    is_call = (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                               and node.func.attr.startswith("assert"))
                    if is_assert or is_call:
                        expression = ast.get_source_segment(source, node)
                        assertions.append({"line": node.lineno, "end_line": node.end_lineno,
                                           "expression": expression,
                                           "sha256": hashlib.sha256(expression.encode()).hexdigest()})
                if assertions:
                    body = ast.get_source_segment(source, function)
                    inventory.append({"path": str(path.relative_to(root)),
                        "test_id": f"tests.{path.stem}.{owner.name}.{function.name}",
                        "test_name": function.name, "line": function.lineno,
                        "end_line": function.end_lineno, "body_sha256": hashlib.sha256(body.encode()).hexdigest(),
                        "file_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                        "assertions": sorted(assertions, key=lambda item: item["line"])})
    return inventory


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


def _apply_review(row: dict[str, object], reviews: dict, bodies: dict, receipt: dict | None) -> None:
    review = reviews.get(row["requirement_id"])
    if not review:
        return
    selected, stale = [], False
    for reference in review.get("tests", []):
        body = bodies.get(reference["test_id"])
        if not body or body["body_sha256"] != reference["body_sha256"]:
            stale = True
        elif body:
            selected.append(body)
    row.update(primary_assertions=selected, review_basis=review.get("review_basis"),
               remaining_gap=review.get("remaining_gap", ""),
               assertion_coverage=review["assertion_coverage"], mapping_kind="explicit_body_review")
    if stale:
        row.update(assertion_coverage="partial", runtime_result="stale",
                   remaining_gap="Assertion body changed after adequacy review; re-review required.")
        return
    if row["assertion_coverage"] == "mapped" and not selected:
        row.update(assertion_coverage="unmapped", remaining_gap="Reviewed assertion body absent.")
    if not receipt or row["assertion_coverage"] != "mapped":
        return
    if receipt.get("product_source") != source_identity():
        row["runtime_result"] = "stale"
        return
    cases = {case["test_id"]: case for case in receipt.get("cases", [])}
    matched = [cases.get(body["test_id"]) for body in selected]
    if any(case and case.get("result") == "failed" for case in matched):
        row["runtime_result"] = "failed"
    elif matched and all(case and case.get("result") == "passed" and
                         case.get("body_sha256") == body["body_sha256"] for case, body in zip(matched, selected)):
        row["runtime_result"] = "passed"


def build(receipt: dict[str, object] | None = None) -> dict[str, object]:
    static = json.loads(STATIC_INVENTORY.read_text(encoding="utf-8"))
    overlay = json.loads(OVERLAY.read_text(encoding="utf-8"))
    mapping_revision = static["source_revision"]
    bodies = assertion_inventory()
    by_name = {}
    for body in bodies:
        by_name.setdefault(body["test_name"], []).append(body)
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

        actual = by_name.get(planned, [])
        row["primary_assertions"] = actual
        if actual:
            # An exact name and an assertion body locate evidence, but semantic
            # adequacy still needs a reviewed mapping, including adverse cases.
            row["assertion_coverage"] = "partial"
            row["mapping_kind"] = "body_located_review_pending"
            row["remaining_gap"] = (str(row.get("remaining_gap", "")) +
                "; current assertion bodies pinned; requirement adequacy review pending").strip("; ")
        else:
            row["assertion_coverage"] = "unmapped"
            row["mapping_kind"] = "no_current_assertion_body"
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

    review_path = REPO / "tests/fixtures/e01/assertion-reviews.json"
    reviews = json.loads(review_path.read_text())["requirements"] if review_path.is_file() else {}
    by_id = {body["test_id"]: body for body in bodies}
    for row in named_rows + unnamed_rows + eval_rows:
        _apply_review(row, reviews, by_id, receipt)
    coverage_counts = {bucket: sum(row["assertion_coverage"] == bucket for row in named_rows)
                       for bucket in ("mapped", "partial", "unmapped", "declaration_only")}

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
        "product_source": source_identity(),
        "evidence_revision": head,
        "assertion_review_manifest": {"path": str(review_path.relative_to(REPO)), "sha256": hashlib.sha256(review_path.read_bytes()).hexdigest() if review_path.is_file() else None},
        "runtime_receipt": receipt,
        "assertion_inventory": bodies,
        "mapping_source_revision": mapping_revision,
        "trusted_base_revision": static.get("trusted_base_revision", mapping_revision),
        "method": "Locate and pin current AST assertion expressions for historical requirement inventory; explicit adequacy review and case receipts required for pass. No suite execution.",
        "input_artifacts": [
            str(STATIC_INVENTORY.relative_to(REPO)),
            str(CACHE_MAP.relative_to(REPO)),
            str(OVERLAY.relative_to(REPO)),
            "docs/evaluation.md",
            "tests/fixtures/e01/assertion-reviews.json",
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    receipt = json.loads(args.receipt.read_text()) if args.receipt else None
    payload = build(receipt)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {args.output} ({payload['summary']['named_plan_tests']} named rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
