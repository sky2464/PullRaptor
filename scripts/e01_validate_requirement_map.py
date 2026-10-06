#!/usr/bin/env python3.12
"""Validate E01 requirement-assertion-fixture map structure (stdlib only)."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MAP_PATH = REPO / "docs" / "acceptance" / "artifacts" / "E01" / "requirement-assertion-fixture-map.json"
STATIC_PATH = REPO / "docs" / "acceptance" / "artifacts" / "E01" / "2026-10-03-static-inventory.json"
try:
    from scripts.e01_build_requirement_map import assertion_inventory, source_identity
except ModuleNotFoundError:
    from e01_build_requirement_map import assertion_inventory, source_identity

OVERLAY_PATH = REPO / "docs" / "acceptance" / "artifacts" / "E01" / "task7-task8-assertion-overlay.json"

PLANNED_TASK7 = {
    "test_clean_warm_corrupt_cache_identical",
    "test_atomic_interrupted_write_miss",
    "test_runtime_schema_change_miss",
    "test_same_blob_different_paths_rebound",
    "test_size_cap",
    "test_full_manifest_resolution_recomputed",
    "test_schema_valid_foreign_cache_ignored",
    "test_shared_permissions_cache_disabled",
    "test_cache_symlink_or_reparse_refused",
    "test_ci_cache_off",
    "test_all_extractor_components_invalidate",
    "test_scope_import_closure_fixed_point",
    "test_unrelated_malformed_file_not_required",
    "test_unresolved_context_required",
    "test_incomplete_discovery_cannot_seal_complete_scope",
    "test_slow_preparation_short_policy_still_bounded",
}
PLANNED_TASK8 = {
    "test_structural_python_complete",
    "test_structural_other_language_partial_exit2",
    "test_explicit_diff_profile_scope_statement",
    "test_config_error_exit3",
    "test_empty_findings_not_safety_claim",
    "test_deleted_line_sarif_side",
    "test_unicode_sarif_character_columns",
    "test_stdout_machine_format_stderr_diagnostics",
    "test_terminal_escape_controls_and_bidi",
    "test_markdown_fence_html_link_breakout",
    "test_links_only_from_trusted_identity",
    "test_uri_reserved_segments_roundtrip",
    "test_report_byte_limit_never_complete",
    "test_requested_and_examined_scope_visible",
    "test_recovery_guidance_not_attacker_commands",
    "test_core_network_disabled",
}


def validate_map(data: dict, root: Path = REPO, receipt: dict | None = None) -> list[str]:
    """Reject unearned or stale result claims without forcing perpetual not_run."""
    errors = []
    current_source = source_identity(root)
    current_bodies = {item["test_id"]: item for item in assertion_inventory(root)}
    receipt = receipt or data.get("runtime_receipt")
    cases = {case["test_id"]: case for case in (receipt or {}).get("cases", [])}
    review_manifest = data.get("assertion_review_manifest")
    if review_manifest:
        import hashlib
        review_path = root / review_manifest["path"]
        if not review_path.is_file() or hashlib.sha256(review_path.read_bytes()).hexdigest() != review_manifest["sha256"]:
            errors.append("assertion adequacy review manifest is stale")
    if receipt and receipt.get("product_source_after", current_source) != current_source:
        errors.append("product source changed during case collection")
    if data.get("product_source") != current_source:
        errors.append("product source manifest is stale")
    for bucket in ("named_requirements", "unnamed_requirements", "evaluation_invariants"):
        for row in data.get(bucket, []):
            requirement = row["requirement_id"]
            result = row.get("runtime_result", "not_run")
            if result not in {"passed", "failed", "not_run", "stale"}:
                errors.append(f"{requirement}: invalid runtime result")
            if result != "passed":
                continue
            bodies = row.get("primary_assertions", [])
            if row.get("assertion_coverage") != "mapped" or row.get("remaining_gap") or not bodies:
                errors.append(f"{requirement}: pass without complete reviewed assertion coverage")
            if not receipt or receipt.get("product_source") != current_source:
                errors.append(f"{requirement}: missing or stale product receipt")
            for body in bodies:
                if not isinstance(body, dict):
                    errors.append(f"{requirement}: declaration or line-only assertion reference")
                    continue
                test_id = body.get("test_id")
                current = current_bodies.get(test_id)
                case = cases.get(test_id)
                if not current or current != body:
                    errors.append(f"{requirement}: assertion body stale or missing: {test_id}")
                if not case or case.get("result") != "passed" or case.get("body_sha256") != body.get("body_sha256"):
                    errors.append(f"{requirement}: case not passed at pinned body: {test_id}")
    criteria = data.get("acceptance_criteria", {})
    if any(criteria.get(item) == "passed" for item in ("E01-A1", "E01-A2", "E01-A3")):
        # A runtime map can never fabricate a separate independent decision.
        if criteria.get("independent_decision") != "accepted" or not criteria.get("independent_review_receipt"):
            errors.append("acceptance pass lacks independent review receipt")
    return errors


class RequirementMapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        try:
            from scripts.e01_build_requirement_map import build
        except ModuleNotFoundError:
            from e01_build_requirement_map import build
        cls.data = build()

    def test_complete_requirement_inventory(self) -> None:
        static = json.loads(STATIC_PATH.read_text(encoding="utf-8"))
        self.assertEqual(len(static["named_plan_inventory"]), 106)
        self.assertEqual(self.data["summary"]["named_plan_tests"], 106)
        self.assertEqual(len(self.data["unnamed_requirements"]), 26)

    def test_task7_task8_overlay_covers_planned_names(self) -> None:
        overlay = json.loads(OVERLAY_PATH.read_text(encoding="utf-8"))
        self.assertEqual(set(overlay["named_task7"]), PLANNED_TASK7)
        self.assertEqual(set(overlay["named_task8"]), PLANNED_TASK8)

    def test_no_stale_or_unearned_pass_claims(self) -> None:
        self.assertEqual(validate_map(self.data), [])

    def test_historical_blob_changes_marked_stale_field_present(self) -> None:
        self.assertIn("mapping_source_revision", self.data)
        self.assertIn("document_revision", self.data)


if __name__ == "__main__":
    raise SystemExit(unittest.main(verbosity=2))
