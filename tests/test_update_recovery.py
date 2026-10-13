"""BR18 real pip transitions against owned, unpublished maintenance fixtures."""
from __future__ import annotations
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "maintenance_rehearsal.py"
_RESULT = None


def rehearsal():
    global _RESULT
    if _RESULT is None:
        if not SCRIPT.is_file():
            raise AssertionError("BR18 real cross-version installer harness is missing")
        spec = importlib.util.spec_from_file_location("maintenance_rehearsal", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        wheelhouse = Path(os.environ.get("PULLRAPTOR_BR18_WHEELHOUSE", ROOT / ".superpowers/sdd/acceptance-maintenance-closure/wheelhouse"))
        with tempfile.TemporaryDirectory(prefix="pullraptor-br18-tests-") as tmp:
            _RESULT = module.run_rehearsal(ROOT, Path(tmp), wheelhouse, ROOT / "tests/fixtures/e07/maintenance/pullraptor-0.1.0b2.dev0-py3-none-any.whl")
    return _RESULT


class TestUpdateRecovery(unittest.TestCase):
    def test_real_distinct_update_and_corrupt_refusal(self):
        receipt = rehearsal()
        self.assertEqual(receipt["prior"]["version"], "0.1.0b1")
        self.assertEqual(receipt["candidate"]["version"], "0.1.0b2.dev0")
        self.assertNotEqual(receipt["candidate"]["sha256"], receipt["prior"]["sha256"])
        corrupt = receipt["scenarios"]["corrupt_candidate"]
        self.assertNotEqual(corrupt["exit_code"], 0)
        self.assertEqual(corrupt["before"], corrupt["after"])
        self.assertEqual(receipt["scenarios"]["successful_update"]["verified"]["version"], "0.1.0b2.dev0")

    def test_interrupted_update_two_actual_filesystem_checkpoints(self):
        receipt = rehearsal()
        for name in ("after_old_dist_info_removal", "after_first_package_write"):
            scenario = receipt["scenarios"][name]
            self.assertTrue(scenario["checkpoint"]["reached"])
            self.assertEqual(scenario["checkpoint"]["name"], name)
            self.assertEqual(scenario["exit_code"], -9)
            self.assertFalse(scenario["interrupted_state"]["old_dist_info_present"])
            self.assertFalse(scenario["interrupted_state"]["candidate_dist_info_present"])
            count = len(scenario["interrupted_state"]["package_files"])
            self.assertEqual(count, 0 if name == "after_old_dist_info_removal" else 1)
            self.assertEqual(scenario["recovered"]["version"], "0.1.0b1")
            self.assertEqual(scenario["retry"]["version"], "0.1.0b2.dev0")
            self.assertEqual(scenario["rollback"]["version"], "0.1.0b1")
            self.assertTrue(scenario["uninstall"]["no_package_remnants"])

    def test_reports_entrypoints_and_identities_after_every_recovery(self):
        receipt = rehearsal()
        for name in ("after_old_dist_info_removal", "after_first_package_write"):
            scenario = receipt["scenarios"][name]
            for stage in ("recovered", "retry", "rollback"):
                verification = scenario[stage]
                self.assertTrue(verification["all_wheel_files_match"])
                self.assertTrue(verification["installed_import_only"])
                self.assertEqual(verification["excluded_commands"], {"publish": 2, "mcp": 2, "workdir": 2, "staged": 2, "cli_mcp": 2, "untracked": 2, "ai": 2})
                self.assertEqual(verification["canonical_sha256"], scenario["baseline"]["canonical_sha256"])
                self.assertTrue(verification["previous_report_preserved"])


class TestCheckpointGuards(unittest.TestCase):
    def test_unreached_checkpoint_cannot_claim_an_interruption(self):
        spec = importlib.util.spec_from_file_location("maintenance_rehearsal", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        wheelhouse = Path(os.environ.get("PULLRAPTOR_BR18_WHEELHOUSE", ROOT / ".superpowers/sdd/acceptance-maintenance-closure/wheelhouse"))
        with tempfile.TemporaryDirectory(prefix="pullraptor-br18-no-checkpoint-") as tmp:
            runner = module.Runner(Path(tmp))
            venv = Path(tmp) / "venv"
            python = module.new_venv(runner, venv, wheelhouse)
            module.pip_install(runner, python, ROOT / "tests/fixtures/e07/pullraptor-0.1.0b1-py3-none-any.whl")
            candidate = ROOT / "tests/fixtures/e07/maintenance/pullraptor-0.1.0b2.dev0-py3-none-any.whl"
            with self.assertRaisesRegex(AssertionError, "checkpoint not reached"):
                module.interrupt_update(runner, venv, candidate, "unreached_checkpoint")
            self.assertTrue(module.filesystem_state(venv)["candidate_dist_info_present"])


class TestReviewedToolBoundary(unittest.TestCase):
    def test_replaced_build_only_tool_bytes_are_refused(self):
        spec = importlib.util.spec_from_file_location("maintenance_rehearsal", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory(prefix="pullraptor-br18-tool-tamper-") as tmp:
            house = Path(tmp)
            (house / "pip-26.2.1-py3-none-any.whl").write_bytes(b"unreviewed replacement")
            with self.assertRaisesRegex(ValueError, "tool hash mismatch: pip"):
                module.inspect_wheelhouse(house)
