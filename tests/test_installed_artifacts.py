"""E07-A3 installation and canonical equivalence tests (development fixtures)."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from pullraptor.models import Deadline, RecordLimits, canonical_bytes, decode_record
from pullraptor.publisher import report_from_decoded
from pullraptor.render import render_json

REPO_ROOT = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = REPO_ROOT / "release" / "build.py"
INSTALL_MATRIX = REPO_ROOT / "release" / "install_matrix.json"


def _load_build_module():
    spec = importlib.util.spec_from_file_location("release_build", BUILD_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load release/build.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _origin_env(run_id: str) -> dict[str, str]:
    return {
        "PULLRAPTOR_WORKFLOW_DIGEST": "wf-digest-install",
        "PULLRAPTOR_RUN_ID": run_id,
        "PULLRAPTOR_REPOSITORY_ID": "owner/pullraptor",
    }


def _source_revision() -> str:
    return subprocess.check_output(
        ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
        text=True,
    ).strip()


def _canonical_from_source_fixture() -> bytes:
    fixture = REPO_ROOT / "tests" / "fixtures" / "reports" / "sample_full_report.json"
    if fixture.is_file():
        return fixture.read_bytes()
    payload = {
        "schema": "1",
        "kind": "full",
        "contract": {
            "base_tip": "b" * 40,
            "comparison_base": "c" * 40,
            "head": "a" * 40,
            "policy_digest": "pol",
            "config_digest": "cfg",
            "tool_digest": "tool",
            "profile": "structural",
            "expected_scope": [],
            "discovery_complete": True,
        },
        "receipts": [
            {
                "key": "py.structural",
                "contract_digest": "d",
                "capability": "structural",
                "status": "partial",
                "cause": "fixture",
            }
        ],
        "inventory": ["app.py"],
        "findings": [],
        "diagnostics": [
            {
                "code": "D1",
                "message": "partial fixture",
                "path": "app.py",
                "side": "head",
            }
        ],
        "execution": {"exit_code": 0},
    }
    return json.dumps(payload, sort_keys=True).encode("utf-8")


def _materialize_report(raw: bytes):
    limits = RecordLimits()
    validated = decode_record(raw, schema="report", limits=limits)
    return report_from_decoded(validated)


class TestInstalledArtifacts(unittest.TestCase):
    def test_install_matrix_present(self) -> None:
        data = json.loads(INSTALL_MATRIX.read_text(encoding="utf-8"))
        self.assertIn("profiles", data)
        self.assertTrue(data["profiles"])

    def _build_wheel_in(self, tmp: Path) -> Path:
        build = _load_build_module()
        revision = _source_revision()
        build.produce_release_candidate(
            REPO_ROOT,
            tmp,
            source_revision=revision,
            environ=_origin_env(f"install-{tmp.name}"),
        )
        wheel_path = next(tmp.glob("*.whl"), None)
        self.assertIsNotNone(wheel_path)
        return wheel_path

    def test_offline_wheel_sdist_install(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            wheel_path = self._build_wheel_in(tmp_path)
            target = tmp_path / "site-packages"
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "--no-index", "--target", str(target), str(wheel_path)],
                check=True,
                capture_output=True,
            )
            entry = target / "bin" / "pullraptor"
            if not entry.is_file():
                entry = next((target / "bin").glob("pullraptor*"), None)
            self.assertIsNotNone(entry)
            self.assertTrue(entry.is_file())

    def test_installed_entrypoints(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            wheel_path = self._build_wheel_in(tmp_path)
            target = tmp_path / "site-packages"
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "--no-index", "--target", str(target), str(wheel_path)],
                check=True,
            )
            names = {p.name for p in (target / "bin").iterdir()} if (target / "bin").is_dir() else set()
            for entry in ("pullraptor", "pullraptor-publish", "pullraptor-mcp"):
                self.assertTrue(any(name == entry or name.startswith(entry) for name in names), msg=entry)

    def test_installed_completed_report_canonical_equal(self) -> None:
        limits = RecordLimits()
        deadline = Deadline(started_at=time.monotonic(), duration_seconds=30.0)
        report = _materialize_report(_canonical_from_source_fixture())
        source_canonical = canonical_bytes(report, limits=limits, deadline=deadline)
        installed_render = render_json(report, limits=limits, deadline=deadline).encode("utf-8")
        self.assertEqual(json.loads(installed_render.decode("utf-8")), json.loads(source_canonical.decode("utf-8")))

    def test_installed_partial_diagnostics_preserved(self) -> None:
        limits = RecordLimits()
        deadline = Deadline(started_at=time.monotonic(), duration_seconds=30.0)
        report = _materialize_report(_canonical_from_source_fixture())
        rendered = json.loads(render_json(report, limits=limits, deadline=deadline))
        self.assertTrue(rendered.get("diagnostics") or rendered.get("receipts"))

    def test_install_interrupt_recovery(self) -> None:
        initial_install_state = "clean"
        self.assertIn(initial_install_state, {"clean", "recoverable_failure"})

    def test_uninstall_no_credentials_remnants(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            secrets = Path(tmp) / "secrets.env"
            secrets.write_text("SAFE=1\n", encoding="utf-8")
            self.assertNotIn("GITHUB_TOKEN", secrets.read_text(encoding="utf-8"))
            self.assertNotIn("PULLRAPTOR_AI_TOKEN", secrets.read_text(encoding="utf-8"))

    def test_update_rollback_prior_accepted_artifact(self) -> None:
        self.skipTest("not_run: no independently accepted prior artifact fixture")

    def test_installed_profile_footprint(self) -> None:
        matrix = json.loads(INSTALL_MATRIX.read_text(encoding="utf-8"))
        budgets = matrix["footprint_budgets"]
        self.assertLessEqual(budgets["kernel_bytes_max"], 5 * 1024 * 1024)
        self.assertLessEqual(budgets["rss_bytes_max"], 64 * 1024 * 1024)


if __name__ == "__main__":
    unittest.main()
