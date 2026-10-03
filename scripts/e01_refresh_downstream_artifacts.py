#!/usr/bin/env python3.12
"""Derive downstream card schedules and runtime cross-refs from the requirement map (stdlib only)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ARTIFACTS = REPO / "docs" / "acceptance" / "artifacts" / "E01"
MAP_PATH = ARTIFACTS / "requirement-assertion-fixture-map.json"
CACHE_MAP = ARTIFACTS / "2026-10-03-cache-output-assertion-map.md"
SCHEDULE_PATH = ARTIFACTS / "downstream-fixture-schedule.json"
XREF_PATH = ARTIFACTS / "cache-output-assertion-map.runtime-xref.json"

CARD_OUTPUT_DIRS: dict[str, str] = {
    "E01-T9-CACHE": "cache",
    "E01-T9-OUTPUT": "output",
    "E01-T9-RECORDS": "boundaries",
    "E01-T9-CORPUS": "corpus",
    "E01-T9-BENCH": "benchmark",
}

U7_FIXTURES = {
    "E01-CACHE-EQUALITY",
    "E01-CACHE-MUTATIONS",
    "E01-CACHE-REPLAY",
    "E01-BOOTSTRAP-DEADLINE",
    "E01-CACHE-CONTENT-BOUNDARY",
    "E01-CACHE-OPERATIONAL",
    "E01-CACHE-ADMISSION",
    "E01-CACHE-IDENTITIES",
    "E01-COORDINATOR-INPUTS",
    "E01-SCOPE-CLOSURE",
    "E01-AGGREGATE-BUDGETS",
    "E01-REVISION-REBUILD",
}
U8_OUTPUT_FIXTURES = {
    "E01-FORMAT-SCOPE",
    "E01-OUTPUT-EXHAUSTION",
    "E01-RENDER-DEADLINE",
    "E01-MINIMUM-OUTPUT-CAPACITY",
    "E01-CLI-OUTPUT-CHANNEL",
    "E01-CLI-OFFLINE-BOUNDARY",
    "E01-PRESENTATION-BOUNDARY",
    "E01-SARIF-SIDES",
    "E01-LOCATION-TO-OUTPUT",
    "E01-RECOVERY-FLOW",
    "E01-RUNTIME-CONTRACT",
}
BENCH_FIXTURES = {"E01-LOCAL-FLOW-INVENTORY", "E01-BENCHMARK-INVENTORY"}
CORPUS_FIXTURES = {"E01-ADVISORY-OUTPUT"}


def _card_for_fixture(proposed: str, req_id: str) -> str:
    if proposed in U7_FIXTURES or req_id.startswith("U7-"):
        return "E01-T9-CACHE"
    if proposed in BENCH_FIXTURES or req_id in {"U8-12", "U8-13"}:
        return "E01-T9-BENCH"
    if proposed in CORPUS_FIXTURES:
        return "E01-T9-CORPUS"
    if proposed in U8_OUTPUT_FIXTURES or req_id.startswith("U8-"):
        return "E01-T9-OUTPUT"
    return "E01-T9-RECORDS"


def _runtime_subset() -> dict[str, object] | None:
    rev_path = ARTIFACTS / "git_revision.txt"
    inv_path = ARTIFACTS / "test_inventory.json"
    exit_path = ARTIFACTS / "unittest_exit_code.txt"
    if not (rev_path.is_file() and inv_path.is_file() and exit_path.is_file()):
        return None
    inventory = json.loads(inv_path.read_text(encoding="utf-8"))
    return {
        "candidate_revision": rev_path.read_text(encoding="utf-8").strip(),
        "collected_at": inventory.get("collected_at"),
        "discovered_test_methods": inventory.get("test_count"),
        "production_module_count": inventory.get("inventory", {}).get(
            "production_module_count"
        ),
        "production_line_count": inventory.get("inventory", {}).get(
            "production_line_count"
        ),
        "unittest_exit_code": int(exit_path.read_text(encoding="utf-8").strip()),
        "unittest_log": "unittest_discover_verbose.log",
        "micro_benchmark": "micro_benchmark.json",
        "claim_limit": "Full-suite pass is subset evidence only; requirement rows remain not_run.",
    }


def build_schedule(requirement_map: dict[str, object]) -> dict[str, object]:
    cards: dict[str, list[dict[str, object]]] = {cid: [] for cid in CARD_OUTPUT_DIRS}
    for row in requirement_map.get("unnamed_requirements", []):
        if not isinstance(row, dict):
            continue
        proposed = str(row.get("proposed_fixture", ""))
        req_id = str(row.get("requirement_id", ""))
        card = _card_for_fixture(proposed, req_id)
        cards[card].append(
            {
                "requirement_id": req_id,
                "proposed_fixture": proposed,
                "acceptance_ids": row.get("acceptance_ids", []),
                "static_coverage": row.get("assertion_coverage"),
                "runtime_result": row.get("runtime_result", "not_run"),
            }
        )

    for row in requirement_map.get("named_requirements", []):
        if not isinstance(row, dict):
            continue
        task = int(row.get("task", 0))
        if task not in range(1, 7):
            continue
        cards["E01-T9-RECORDS"].append(
            {
                "requirement_id": row.get("requirement_id"),
                "planned_test": row.get("planned_test"),
                "assertion_coverage": row.get("assertion_coverage"),
                "runtime_result": row.get("runtime_result", "not_run"),
            }
        )

    task7 = [
        r
        for r in requirement_map.get("named_requirements", [])
        if isinstance(r, dict) and r.get("task") == 7
    ]
    task8 = [
        r
        for r in requirement_map.get("named_requirements", [])
        if isinstance(r, dict) and r.get("task") == 8
    ]
    for row in task7:
        cards["E01-T9-CACHE"].append(
            {
                "requirement_id": row.get("requirement_id"),
                "planned_test": row.get("planned_test"),
                "assertion_coverage": row.get("assertion_coverage"),
                "runtime_result": row.get("runtime_result", "not_run"),
            }
        )
    for row in task8:
        cards["E01-T9-OUTPUT"].append(
            {
                "requirement_id": row.get("requirement_id"),
                "planned_test": row.get("planned_test"),
                "assertion_coverage": row.get("assertion_coverage"),
                "runtime_result": row.get("runtime_result", "not_run"),
            }
        )

    return {
        "kind": "downstream_fixture_schedule",
        "date": datetime.now(timezone.utc).date().isoformat(),
        "source_artifacts": [
            str(MAP_PATH.relative_to(REPO)),
            str(CACHE_MAP.relative_to(REPO)),
        ],
        "mapping_source_revision": requirement_map.get("mapping_source_revision"),
        "document_revision": requirement_map.get("document_revision"),
        "acceptance_criteria": requirement_map.get("acceptance_criteria"),
        "cards": cards,
        "output_directories": CARD_OUTPUT_DIRS,
        "claim_limit": "Schedules proposed fixtures and gaps; does not pass criteria or create fixtures.",
    }


def _write_card_stubs(schedule: dict[str, object]) -> None:
    cards = schedule.get("cards", {})
    if not isinstance(cards, dict):
        return
    for card_id, subdir in CARD_OUTPUT_DIRS.items():
        out_dir = ARTIFACTS / subdir
        out_dir.mkdir(parents=True, exist_ok=True)
        entries = cards.get(card_id, [])
        index = {
            "card_id": card_id,
            "artifact_directory": subdir,
            "scheduled_rows": len(entries) if isinstance(entries, list) else 0,
            "evidence_status": "not_run",
            "claim_limit": "Placeholder until the assigned card saves fixtures and raw outputs.",
        }
        (out_dir / "index.json").write_text(
            json.dumps(index, indent=2) + "\n", encoding="utf-8"
        )


def main() -> int:
    if not MAP_PATH.is_file():
        raise SystemExit(f"Missing {MAP_PATH}; run e01_build_requirement_map.py first.")
    requirement_map = json.loads(MAP_PATH.read_text(encoding="utf-8"))
    schedule = build_schedule(requirement_map)
    SCHEDULE_PATH.write_text(json.dumps(schedule, indent=2) + "\n", encoding="utf-8")

    runtime = _runtime_subset()
    xref = {
        "kind": "cache_output_assertion_map_runtime_xref",
        "date": datetime.now(timezone.utc).date().isoformat(),
        "static_map": CACHE_MAP.name,
        "static_map_revision": requirement_map.get("mapping_source_revision"),
        "runtime_subset": runtime,
        "downstream_schedule": SCHEDULE_PATH.name,
        "claim_limit": "Static Task 7–8 body review remains bound to mapping_source_revision; "
        "this file links separately collected runtime subset evidence only.",
    }
    XREF_PATH.write_text(json.dumps(xref, indent=2) + "\n", encoding="utf-8")

    if runtime is not None:
        requirement_map["runtime_subset"] = runtime
        requirement_map["downstream_schedule_artifact"] = str(
            SCHEDULE_PATH.relative_to(REPO)
        )
        MAP_PATH.write_text(json.dumps(requirement_map, indent=2) + "\n", encoding="utf-8")

    _write_card_stubs(schedule)
    print(f"Wrote {SCHEDULE_PATH} and {XREF_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
