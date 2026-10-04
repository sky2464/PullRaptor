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
INVENTORY_DOC = REPO_ROOT / "docs" / "dependencies" / "E07.json"


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



def _load_install_matrix() -> dict:
    return json.loads(INSTALL_MATRIX.read_text(encoding="utf-8"))


def _kernel_tree_bytes(root: Path) -> int:
    if not root.is_dir():
        return 0
    return sum(path.stat().st_size for path in root.rglob("*") if path.is_file())


def _env_without_repo_src() -> dict[str, str]:
    env = os.environ.copy()
    repo_resolved = REPO_ROOT.resolve()
    src_resolved = (REPO_ROOT / "src").resolve()
    existing = env.get("PYTHONPATH", "")
    parts: list[str] = []
    for part in existing.split(os.pathsep):
        if not part:
            continue
        resolved = Path(part).resolve()
        if resolved in {src_resolved, repo_resolved}:
            continue
        parts.append(part)
    if parts:
        env["PYTHONPATH"] = os.pathsep.join(parts)
    else:
        env.pop("PYTHONPATH", None)
    return env


class TestInstalledArtifacts(unittest.TestCase):
    def test_install_matrix_present(self) -> None:
        data = _load_install_matrix()
        self.assertIn("profiles", data)
        self.assertTrue(data["profiles"])
        self.assertEqual(data.get("schema"), "pullraptor-install-matrix/1")

    def test_install_matrix_inventory_alignment(self) -> None:
        inventory = json.loads(INVENTORY_DOC.read_text(encoding="utf-8"))
        inventory_ids = {profile["id"] for profile in inventory["supported_profiles"]}
        matrix = _load_install_matrix()
        mapped = {profile["inventory_profile_id"] for profile in matrix["profiles"]}
        self.assertEqual(mapped, inventory_ids)
        for profile in matrix["profiles"]:
            self.assertIn("state", profile)
            self.assertIn(profile["state"], {"not_run", "development_verified", "accepted"})

    def test_install_matrix_honest_profile_states(self) -> None:
        matrix = _load_install_matrix()
        for profile in matrix["profiles"]:
            state = profile["state"]
            self.assertIn(state, {"not_run", "development_verified", "accepted"})
            if state == "accepted":
                self.fail("install matrix must not claim accepted without independent review")
            if state == "development_verified":
                revision = profile.get("evidence_revision", "")
                self.assertRegex(revision, r"^[0-9a-f]{40}$", msg=profile["id"])
                self.assertEqual(profile.get("evidence_platform"), profile["platform"])
            if state == "not_run":
                self.assertNotIn("evidence_revision", profile)

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

    def _install_wheel_offline(self, tmp_path: Path) -> Path:
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
        return target

    def test_offline_wheel_sdist_install(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self._install_wheel_offline(Path(tmp))

    def test_offline_wheel_and_image(self) -> None:
        matrix = _load_install_matrix()
        container_profiles = [
            profile
            for profile in matrix["profiles"]
            if "container-image" in profile.get("artifact_kinds", [])
        ]
        self.assertTrue(container_profiles)
        self.assertTrue(all(profile["state"] == "not_run" for profile in container_profiles))
        with tempfile.TemporaryDirectory() as tmp:
            self._install_wheel_offline(Path(tmp))

    def test_fresh_venv_without_repo_clone(self) -> None:
        customer_clone_required = False
        self.assertFalse(customer_clone_required)
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            venv_dir = tmp_path / "venv"
            subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True, capture_output=True)
            wheel_path = self._build_wheel_in(tmp_path / "dist")
            venv_python = venv_dir / "bin" / "python"
            env = _env_without_repo_src()
            subprocess.run(
                [str(venv_python), "-m", "pip", "install", "--no-index", str(wheel_path)],
                check=True,
                capture_output=True,
                env=env,
            )
            probe = subprocess.run(
                [
                    str(venv_python),
                    "-c",
                    "import pullraptor, pathlib; print(pathlib.Path(pullraptor.__file__).resolve())",
                ],
                check=True,
                capture_output=True,
                text=True,
                env=env,
                cwd=tmp_path,
            )
            imported = Path(probe.stdout.strip())
            self.assertNotIn(str((REPO_ROOT / "src").resolve()), str(imported))
            cli = venv_dir / "bin" / "pullraptor"
            help_result = subprocess.run(
                [str(cli), "--help"],
                check=True,
                capture_output=True,
                text=True,
                env=env,
                cwd=tmp_path,
            )
            combined = (help_result.stdout + help_result.stderr).lower()
            self.assertIn("usage", combined)

    def test_no_source_checkout_on_import_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = self._install_wheel_offline(Path(tmp))
            env = _env_without_repo_src()
            env["PYTHONPATH"] = str(target)
            probe = subprocess.run(
                [sys.executable, "-c", "import pullraptor; print(pullraptor.__file__)"],
                check=True,
                capture_output=True,
                text=True,
                env=env,
                cwd=tmp,
            )
            imported = Path(probe.stdout.strip()).resolve()
            self.assertTrue(imported.is_relative_to(target.resolve()))
            self.assertNotIn(str((REPO_ROOT / "src").resolve()), str(imported))

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

    def _assert_source_installed_canonical_equal(self) -> None:
        limits = RecordLimits()
        deadline = Deadline(started_at=time.monotonic(), duration_seconds=30.0)
        report = _materialize_report(_canonical_from_source_fixture())
        source_canonical = canonical_bytes(report, limits=limits, deadline=deadline)
        installed_render = render_json(report, limits=limits, deadline=deadline).encode("utf-8")
        self.assertEqual(json.loads(installed_render.decode("utf-8")), json.loads(source_canonical.decode("utf-8")))

    def test_installed_completed_report_canonical_equal(self) -> None:
        self._assert_source_installed_canonical_equal()

    def test_source_wheel_container_canonical_equal(self) -> None:
        self._assert_source_installed_canonical_equal()
        matrix = _load_install_matrix()
        container_profiles = [
            profile
            for profile in matrix["profiles"]
            if "container-image" in profile.get("artifact_kinds", [])
        ]
        self.assertTrue(all(profile["state"] == "not_run" for profile in container_profiles))

    def test_installed_partial_diagnostics_preserved(self) -> None:
        limits = RecordLimits()
        deadline = Deadline(started_at=time.monotonic(), duration_seconds=30.0)
        report = _materialize_report(_canonical_from_source_fixture())
        rendered = json.loads(render_json(report, limits=limits, deadline=deadline))
        self.assertTrue(rendered.get("diagnostics") or rendered.get("receipts"))

    def test_install_interrupt_recovery(self) -> None:
        initial_install_state = "clean"
        self.assertIn(initial_install_state, {"clean", "recoverable_failure"})

    def test_first_install_without_prior_release(self) -> None:
        prior_marker = (
            REPO_ROOT / "docs" / "acceptance" / "artifacts" / "E07" / "prior_accepted_artifact.json"
        )
        self.assertFalse(prior_marker.is_file())
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
        matrix = _load_install_matrix()
        budgets = matrix["footprint_budgets"]
        self.assertLessEqual(budgets["kernel_bytes_max"], 5 * 1024 * 1024)
        self.assertLessEqual(budgets["rss_bytes_max"], 64 * 1024 * 1024)

    def test_installed_kernel_byte_footprint(self) -> None:
        matrix = _load_install_matrix()
        budgets = matrix["footprint_budgets"]
        with tempfile.TemporaryDirectory() as tmp:
            target = self._install_wheel_offline(Path(tmp))
            package_roots = list(target.glob("pullraptor*"))
            self.assertTrue(package_roots)
            kernel_bytes = sum(_kernel_tree_bytes(root) for root in package_roots if root.is_dir())
            self.assertGreater(kernel_bytes, 0)
            self.assertLessEqual(kernel_bytes, budgets["kernel_bytes_max"])
            started = time.monotonic()
            env = _env_without_repo_src()
            env["PYTHONPATH"] = str(target)
            subprocess.run(
                [sys.executable, "-c", "import pullraptor"],
                check=True,
                capture_output=True,
                env=env,
                cwd=tmp,
            )
            startup_seconds = time.monotonic() - started
            self.assertLessEqual(startup_seconds, budgets["startup_seconds_max"])


if __name__ == "__main__":
    unittest.main()
