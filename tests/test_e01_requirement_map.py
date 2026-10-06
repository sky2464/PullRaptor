"""E01-T9-MAP structural validation (card test names)."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MAP_PATH = REPO / "docs" / "acceptance" / "artifacts" / "E01" / "requirement-assertion-fixture-map.json"
STATIC_PATH = REPO / "docs" / "acceptance" / "artifacts" / "E01" / "2026-10-03-static-inventory.json"
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


class TestE01RequirementMap(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not MAP_PATH.is_file():
            subprocess.run(
                [sys.executable, str(REPO / "scripts" / "e01_build_requirement_map.py")],
                cwd=REPO,
                check=True,
            )
        cls.data = json.loads(MAP_PATH.read_text(encoding="utf-8"))

    def test_complete_requirement_inventory(self) -> None:
        static = json.loads(STATIC_PATH.read_text(encoding="utf-8"))
        self.assertEqual(len(static["named_plan_inventory"]), 106)
        self.assertEqual(self.data["summary"]["named_plan_tests"], 106)
        self.assertEqual(len(self.data["unnamed_requirements"]), 26)

    def test_task7_task8_overlay_covers_planned_names(self) -> None:
        overlay = json.loads(OVERLAY_PATH.read_text(encoding="utf-8"))
        self.assertEqual(set(overlay["named_task7"]), PLANNED_TASK7)
        self.assertEqual(set(overlay["named_task8"]), PLANNED_TASK8)

    def test_no_acceptance_pass_claims(self) -> None:
        criteria = self.data["acceptance_criteria"]
        self.assertEqual(criteria["E01-A1"], "not_run")
        self.assertEqual(criteria["E01-A2"], "not_run")
        self.assertEqual(criteria["E01-A3"], "not_run")
        self.assertEqual(criteria["independent_decision"], "pending")
        for row in self.data["named_requirements"]:
            self.assertEqual(row["runtime_result"], "not_run")

    def test_historical_blob_changes_marked_stale_field_present(self) -> None:
        self.assertIn("mapping_source_revision", self.data)
        self.assertIn("document_revision", self.data)
        head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO,
            text=True,
        ).strip()
        self.assertEqual(self.data["document_revision"], head)


if __name__ == "__main__":
    raise SystemExit(unittest.main(verbosity=2))
