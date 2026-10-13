#!/usr/bin/env python3
"""BR18 owned development fixture rehearsal; no updater or release authority.

All installations use pinned pip, disposable venvs and an offline wheelhouse.
The unpublished candidate comes from a separately committed trusted source
fixture. The two interrupted operations call pip's real filesystem functions,
then block until the parent observes the required state and kills the group.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
import time
import zipfile

BASE_REVISION = "48bef09d985fbeb42749d1cc6238c74429616a25"
PRIOR_SHA256 = "d44d6da0e6fc667a26260896cd5f4d82c35b59f8126e65ce38d92d9a8e97be24"
CANDIDATE_VERSION = "0.1.0b2.dev0"
PINS = {"pip": "26.2.1", "setuptools": "84.0.0", "wheel": "0.48.0", "packaging": "26.0"}
TOOL_HASHES = {
    "pip": "71138adf1f4ca900cdb7d289c21b7494329f2332b6d85f0e1c42108c0384ed3e",
    "setuptools": "51a52592b3b99e102b609654876bd65f19f999935166d1352678931132b0c670",
    "wheel": "3217dcc807155e45db462d7ef2431f5ddda0d7273b700d05a67b271ceb1287ab",
    "packaging": "b36f1fef9334a5588b4166f8bcd26a14e521f2b55e6b9de3aaa80d3ff7a37529",
}
HELPER = Path(__file__).with_name("_maintenance_installer.py")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def clean_env(root):
    """Explicit allowlist; no ambient credentials, startup paths or caches."""
    home = root / "home"
    home.mkdir(exist_ok=True)
    return {"PATH": os.pathsep.join(dict.fromkeys([str(Path(sys.executable).parent), "/opt/homebrew/bin", "/usr/bin", "/bin"])),
            "HOME": str(home), "TMPDIR": str(root), "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8",
            "PIP_CONFIG_FILE": os.devnull, "PIP_NO_INDEX": "1", "PIP_DISABLE_PIP_VERSION_CHECK": "1",
            "PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1", "SOURCE_DATE_EPOCH": "0",
            "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_AUTHOR_NAME": "PullRaptor Fixture", "GIT_AUTHOR_EMAIL": "fixture@localhost",
            "GIT_COMMITTER_NAME": "PullRaptor Fixture", "GIT_COMMITTER_EMAIL": "fixture@localhost",
            "GIT_AUTHOR_DATE": "2000-01-01T00:00:00Z", "GIT_COMMITTER_DATE": "2000-01-01T00:00:00Z"}


class Runner:
    def __init__(self, root):
        self.root = root
        self.env = clean_env(root)
        self.commands = []

    def run(self, args, expected=0, cwd=None):
        args = [str(x) for x in args]
        result = subprocess.run(args, cwd=cwd or self.root, env=self.env,
                                text=True, capture_output=True, timeout=120)
        self.commands.append({"argv": args, "cwd": str(cwd or self.root),
                              "exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr})
        if expected is not None and result.returncode != expected:
            raise AssertionError(f"command exit {result.returncode} expected {expected}: {args}\n{result.stderr}\n{result.stdout}")
        return result


def inspect_wheelhouse(wheelhouse):
    ledger = []
    for name, version in PINS.items():
        path = wheelhouse / f"{name}-{version}-py3-none-any.whl"
        if not path.is_file():
            raise ValueError(f"missing reviewed build-only wheel: {path}")
        if digest(path) != TOOL_HASHES[name]:
            raise ValueError(f"reviewed build-only tool hash mismatch: {name}")
        with zipfile.ZipFile(path) as wheel:
            metadata = wheel.read(next(n for n in wheel.namelist() if n.endswith("/METADATA"))).decode()
            requirements = [line.removeprefix("Requires-Dist: ") for line in metadata.splitlines() if line.startswith("Requires-Dist:")]
            license_fields = [line for line in metadata.splitlines() if line.startswith(("License:", "License-Expression:", "License-File:"))]
        ledger.append({"name": name, "version": version, "sha256": digest(path), "bytes": path.stat().st_size,
                       "role": "test installer/build only; not customer runtime", "requirements": requirements,
                       "license_metadata": license_fields})
    return ledger


def new_venv(run, location, wheelhouse, build=False):
    run.run([sys.executable, "-I", "-m", "venv", location])
    python = location / "bin/python"
    names = list(PINS) if build else ["pip"]
    run.run([python, "-I", "-m", "pip", "install", "--no-index", "--no-deps", "--no-cache-dir", "--no-compile",
             *[wheelhouse / f"{name}-{PINS[name]}-py3-none-any.whl" for name in names]])
    probe = run.run([python, "-I", "-c", "import importlib.metadata as m; print(m.version('pip'))"])
    if probe.stdout.strip() != PINS["pip"]:
        raise AssertionError("unpinned installer")
    return python


def prepare_candidate(source, destination, wheelhouse, run):
    """Derive only trusted packaging/source inputs into a private committed repo."""
    destination.mkdir(parents=True, exist_ok=True)
    fixture = run.root / "private-candidate-source"
    fixture.mkdir()
    archive = subprocess.run(["git", "-C", str(source), "archive", BASE_REVISION, "src", "pyproject.toml", "README.md"],
                             cwd=run.root, env=run.env, capture_output=True, check=True)
    with tarfile.open(fileobj=io.BytesIO(archive.stdout)) as tar:
        tar.extractall(fixture, filter="data")
    changes = []
    for relative in ("pyproject.toml", "src/pullraptor/__init__.py"):
        path = fixture / relative
        original = path.read_bytes()
        changed = original.replace(b'0.1.0b1', CANDIDATE_VERSION.encode())
        if changed == original:
            raise AssertionError("candidate version change not applied")
        path.write_bytes(changed)
        changes.append({"path": relative, "before_sha256": hashlib.sha256(original).hexdigest(), "after_sha256": digest(path)})
    marker = fixture / "src/pullraptor/maintenance_fixture.py"
    marker.write_text('"""Unpublished BR18 source identity fixture; no runtime behavior change."""\nFIXTURE_ID = "BR18-0.1.0b2.dev0"\n')
    changes.append({"path": str(marker.relative_to(fixture)), "before_sha256": None, "after_sha256": digest(marker)})
    run.run(["git", "init", "--initial-branch=feat/br18-private-fixture", fixture])
    run.run(["git", "-C", fixture, "add", "."])
    run.run(["git", "-C", fixture, "commit", "-m", "test: private unpublished BR18 version fixture"])
    commit = run.run(["git", "-C", fixture, "rev-parse", "HEAD"]).stdout.strip()
    tree = run.run(["git", "-C", fixture, "rev-parse", "HEAD^{tree}"]).stdout.strip()
    tar_bytes = subprocess.run(["git", "-C", str(fixture), "archive", "HEAD"], cwd=run.root, env=run.env, check=True, capture_output=True).stdout
    archive_path = destination / "candidate-source.tar"
    archive_path.write_bytes(tar_bytes)
    bundle_path = destination / "candidate-source.bundle"
    run.run(["git", "-C", fixture, "bundle", "create", bundle_path, "HEAD"])
    python = new_venv(run, run.root / "build-venv", wheelhouse, build=True)
    run.run([python, "-I", "-m", "pip", "wheel", "--no-index", "--no-deps", "--no-build-isolation", "--no-cache-dir",
             "--wheel-dir", destination, fixture])
    wheel_path = destination / f"pullraptor-{CANDIDATE_VERSION}-py3-none-any.whl"
    manifest = {"schema": "pullraptor-br18-private-candidate/1", "version": CANDIDATE_VERSION,
                "trusted_base": BASE_REVISION, "private_source_commit": commit, "private_source_tree": tree,
                "source_archive_sha256": digest(archive_path), "source_bundle_sha256": digest(bundle_path), "wheel_sha256": digest(wheel_path), "changes": changes,
                "public_release": False, "runtime_dependencies": [], "build_tools": inspect_wheelhouse(wheelhouse)}
    write_json(destination / "candidate-provenance.json", manifest)
    return wheel_path


def archive_files(raw):
    with tarfile.open(fileobj=io.BytesIO(raw)) as tar:
        return {m.name: tar.extractfile(m).read() for m in tar.getmembers() if m.isfile()}


def verify_candidate_source(source, candidate, provenance, run):
    """Check fixture and package bytes against explicit trusted-base changes."""
    archived = subprocess.run(["git", "-C", str(source), "archive", BASE_REVISION,
                               "src", "pyproject.toml", "README.md"],
                              env=run.env, cwd=run.root, check=True, capture_output=True).stdout
    expected = archive_files(archived)
    changes = []
    for name in ("pyproject.toml", "src/pullraptor/__init__.py"):
        before = expected[name]
        expected[name] = before.replace(b"0.1.0b1", CANDIDATE_VERSION.encode())
        changes.append({"path": name, "before_sha256": hashlib.sha256(before).hexdigest(),
                        "after_sha256": hashlib.sha256(expected[name]).hexdigest()})
    name = "src/pullraptor/maintenance_fixture.py"
    expected[name] = b'"""Unpublished BR18 source identity fixture; no runtime behavior change."""\nFIXTURE_ID = "BR18-0.1.0b2.dev0"\n'
    changes.append({"path": name, "before_sha256": None, "after_sha256": hashlib.sha256(expected[name]).hexdigest()})
    bundle_path = candidate.parent / "candidate-source.bundle"
    if digest(bundle_path) != provenance["source_bundle_sha256"]:
        raise AssertionError("private fixture git bundle digest mismatch")
    private_repo = run.root / "verified-private-source.git"
    run.run(["git", "clone", "--bare", bundle_path, private_repo])
    commit = run.run(["git", "-C", private_repo, "rev-parse", "HEAD"]).stdout.strip()
    tree = run.run(["git", "-C", private_repo, "rev-parse", "HEAD^{tree}"]).stdout.strip()
    if (commit, tree) != (provenance["private_source_commit"], provenance["private_source_tree"]):
        raise AssertionError("private fixture committed source identity mismatch")
    private_archive = subprocess.run(["git", "-C", str(private_repo), "archive", "HEAD"],
                                     env=run.env, cwd=run.root, check=True, capture_output=True).stdout
    if private_archive != (candidate.parent / "candidate-source.tar").read_bytes():
        raise AssertionError("source archive does not match private committed fixture")
    actual = archive_files(private_archive)
    if actual != expected or provenance["changes"] != changes:
        raise AssertionError("candidate source differs from explicit trusted-base fixture changes")
    with zipfile.ZipFile(candidate) as wheel:
        packaged = {"src/" + n: wheel.read(n) for n in wheel.namelist() if n.startswith("pullraptor/") and not n.endswith("/")}
    if packaged != {n: raw for n, raw in expected.items() if n.startswith("src/pullraptor/")}:
        raise AssertionError("candidate package bytes differ from committed fixture source")


def wheel_identity(wheel_path, version):
    with zipfile.ZipFile(wheel_path) as wheel:
        metadata = wheel.read(f"pullraptor-{version}.dist-info/METADATA").decode()
        if f"Version: {version}\n" not in metadata or "Requires-Dist:" in metadata:
            raise AssertionError("candidate metadata/version/runtime dependencies mismatch")
    return {"version": version, "sha256": digest(wheel_path), "bytes": wheel_path.stat().st_size}


def filesystem_state(venv):
    site = venv / "lib/python3.12/site-packages"
    package = site / "pullraptor"
    names = sorted(p for p in site.glob("*ullraptor*") if p.is_dir())
    files = {}
    for directory in names:
        for path in sorted(directory.rglob("*")):
            if path.is_file():
                files[str(path.relative_to(venv))] = digest(path)
    entries = {p.name: digest(p) for p in (venv / "bin").glob("pullraptor*") if p.is_file()}
    return {"old_dist_info_present": (site / "pullraptor-0.1.0b1.dist-info").exists(),
            "candidate_dist_info_present": (site / f"pullraptor-{CANDIDATE_VERSION}.dist-info").exists(),
            "package_files": sorted(str(p.relative_to(site)) for p in package.rglob("*") if p.is_file()),
            "files": files, "entrypoints": entries, "directories": [p.name for p in names]}


def pip_install(run, python, wheel, force=False, expected=0):
    return run.run([python, "-I", "-m", "pip", "install", "--no-index", "--no-deps", "--no-cache-dir", "--no-compile",
                    "--force-reinstall" if force else "--upgrade", wheel], expected=expected)


def review_fixture(run):
    repo = run.root / "owned-review-fixture"
    repo.mkdir()
    run.run(["git", "init", "--initial-branch=main", repo])
    (repo / "app.py").write_text("def f():\n    return 1\n")
    run.run(["git", "-C", repo, "add", "."])
    run.run(["git", "-C", repo, "commit", "-m", "base"])
    base = run.run(["git", "-C", repo, "rev-parse", "HEAD"]).stdout.strip()
    (repo / "app.py").write_text("import missing_br18_context\ndef f(values=[]):\n    values.append(1)\n    return values\n")
    (repo / "unsupported.js").write_text("export const n = 1;\n")
    run.run(["git", "-C", repo, "add", "."])
    run.run(["git", "-C", repo, "commit", "-m", "advisory and coverage gap"])
    head = run.run(["git", "-C", repo, "rev-parse", "HEAD"]).stdout.strip()
    return repo, base, head


def verify_installed(run, venv, wheel_path, version, review, report, previous=None):
    python = venv / "bin/python"
    site = venv / "lib/python3.12/site-packages"
    probe = run.run([python, "-I", "-c",
                    "import importlib.metadata as m,json,pathlib,pullraptor; d=m.distribution('pullraptor'); "
                    "print(json.dumps({'version':d.version,'module_version':pullraptor.__version__,'import_path':str(pathlib.Path(pullraptor.__file__).resolve()),'distributions':[x.version for x in m.distributions() if x.metadata['Name']=='pullraptor'],'entrypoints':{e.name:e.value for e in d.entry_points}}))"])
    data = json.loads(probe.stdout)
    if data["version"] != version or data["module_version"] != version or data["distributions"] != [version]:
        raise AssertionError(f"mixed installation/distribution: {data}")
    if not Path(data["import_path"]).is_relative_to(site.resolve()):
        raise AssertionError("source-checkout import detected")
    expected_entries = {"pullraptor": "pullraptor.__main__:main", "pullraptor-publish": "pullraptor.publisher:main", "pullraptor-mcp": "pullraptor.mcp_server:console_main"}
    if data["entrypoints"] != expected_entries:
        raise AssertionError("entrypoint metadata differs")
    with zipfile.ZipFile(wheel_path) as wheel:
        package_names = sorted(n for n in wheel.namelist() if n.startswith("pullraptor/") and not n.endswith("/"))
        for name in wheel.namelist():
            if name.endswith("/") or name.endswith("/RECORD"):
                continue
            path = site / name
            if not path.is_file() or path.read_bytes() != wheel.read(name):
                raise AssertionError(f"installed wheel file identity mismatch: {name}")
        actual_names = sorted(str(p.relative_to(site)) for p in (site / "pullraptor").rglob("*") if p.is_file() and "__pycache__" not in p.parts)
        if actual_names != package_names:
            raise AssertionError("foreign or stale installed package files")
    cli = venv / "bin/pullraptor"
    run.run([cli, "--help"])
    excluded = {}
    for name, command in {"publish": [venv / "bin/pullraptor-publish", "--help"],
                          "mcp": [venv / "bin/pullraptor-mcp", "--help"],
                          "workdir": [cli, "--workdir"], "staged": [cli, "--staged"],
                          "cli_mcp": [cli, "--mcp"], "untracked": [cli, "--include-untracked"],
                          "ai": [cli, "--ai-endpoint", "https://invalid.invalid"]}.items():
        excluded[name] = run.run(command, expected=2).returncode
    repo, base, head = review
    reviewed = run.run([cli, "--repo", repo, "--base", base, "--head", head, "--exact-base", "--format", "json", "--no-cache"], expected=2)
    logical = json.loads(reviewed.stdout)
    if not logical.get("findings") or not logical.get("diagnostics") or not any(x["status"] != "complete" for x in logical["receipts"]):
        raise AssertionError("review fixture did not preserve advisory and explicit coverage gap")
    canonical = reviewed.stdout.encode()
    if previous is not None and canonical != previous:
        raise AssertionError("canonical review changed across installation/recovery")
    preserved = not report.exists() or report.read_bytes() == (previous if previous is not None else canonical)
    if not preserved:
        raise AssertionError("previous customer report changed")
    if not report.exists():
        report.write_bytes(canonical)
    return {**data, "all_wheel_files_match": True, "installed_import_only": True,
            "excluded_commands": excluded, "canonical_sha256": hashlib.sha256(canonical).hexdigest(),
            "previous_report_preserved": preserved, "filesystem": filesystem_state(venv)}, canonical


def interrupt_update(run, venv, candidate, checkpoint):
    site = venv / "lib/python3.12/site-packages"
    event = run.root / f"{checkpoint}.json"
    command = [str(venv / "bin/python"), "-I", str(HELPER), str(event), checkpoint, str(site),
               "install", "--no-index", "--no-deps", "--no-cache-dir", "--no-compile", "--upgrade", str(candidate)]
    stdout, stderr = run.root / f"{checkpoint}.stdout", run.root / f"{checkpoint}.stderr"
    with stdout.open("w") as out, stderr.open("w") as err:
        process = subprocess.Popen(command, cwd=run.root, env=run.env, stdin=subprocess.PIPE,
                                   stdout=out, stderr=err, start_new_session=True)
        try:
            until = time.monotonic() + 45
            event_data = None
            while process.poll() is None and time.monotonic() < until:
                if event.is_file():
                    try:
                        event_data = json.loads(event.read_text())
                    except json.JSONDecodeError:
                        pass
                    if event_data is not None:
                        break
                time.sleep(0.01)
            if event_data is None:
                raise AssertionError(f"checkpoint not reached: {checkpoint}: {stderr.read_text()}")
            interrupted_state = filesystem_state(venv)
            os.killpg(process.pid, signal.SIGKILL)
            code = process.wait(timeout=10)
            if code != -signal.SIGKILL:
                raise AssertionError("interrupted installer did not terminate by SIGKILL")
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=10)
            process.stdin.close()
            out.flush()
            err.flush()
            run.commands.append({"argv": command, "cwd": str(run.root), "exit_code": process.returncode,
                                 "stdout": stdout.read_text(), "stderr": stderr.read_text()})
    return {"checkpoint": event_data, "interrupted_state": interrupted_state, "exit_code": code,
            "termination": "killpg(SIGKILL) after observed filesystem checkpoint"}


def repair_orphans(run, venv):
    """Explicit operator cleanup of pip's interrupted uninstall stashes only."""
    site = venv / "lib/python3.12/site-packages"
    removed = []
    for path in sorted(site.glob("~ullraptor*")):
        if path.is_symlink() or not path.is_dir():
            raise AssertionError("unexpected interrupted installer stash")
        removed.append({"path": str(path.relative_to(venv)), "files": {str(p.relative_to(path)): digest(p) for p in path.rglob("*") if p.is_file()}})
        shutil.rmtree(path)
    for path in sorted(run.root.glob("pip-uninstall-*")):
        if path.is_symlink() or not path.is_dir():
            raise AssertionError("unexpected installer temporary stash")
        files = {str(p.relative_to(path)): digest(p) for p in path.rglob("*") if p.is_file()}
        if any(name not in {"pullraptor", "pullraptor-publish", "pullraptor-mcp"} for name in files):
            raise AssertionError("foreign file in installer script stash")
        removed.append({"path": str(path.relative_to(run.root)), "files": files})
        shutil.rmtree(path)
    return removed


def uninstall(run, venv, report, canonical):
    run.run([venv / "bin/python", "-I", "-m", "pip", "uninstall", "--yes", "pullraptor"])
    state = filesystem_state(venv)
    if state["directories"] or state["entrypoints"]:
        raise AssertionError(f"uninstall left package/installer remnants: {state}")
    if report.read_bytes() != canonical:
        raise AssertionError("uninstall mutated previous report")
    credential_names = {".env", "credentials.json", "tokens.json", "secrets.env", "credentials"}
    credential_artifacts = sorted(str(p.relative_to(venv)) for p in venv.rglob("*") if p.is_file() and p.name in credential_names)
    if credential_artifacts:
        raise AssertionError("unexpected credential artifact in disposable venv")
    return {"no_package_remnants": True, "previous_report_preserved": True, "filesystem": state,
            "credential_artifacts": credential_artifacts, "credential_scan_basenames": sorted(credential_names),
            "environment_credentials_passed": False}


def run_rehearsal(source, output, wheelhouse, candidate=None):
    source, output, wheelhouse = Path(source).resolve(), Path(output).resolve(), Path(wheelhouse).resolve()
    if sys.version_info[:2] != (3, 12):
        raise ValueError("Python 3.12 required")
    output.mkdir(parents=True, exist_ok=True)
    ledger = inspect_wheelhouse(wheelhouse)
    prior = source / "tests/fixtures/e07/pullraptor-0.1.0b1-py3-none-any.whl"
    if digest(prior) != PRIOR_SHA256:
        raise AssertionError("accepted prior artifact changed")
    receipt = {"schema": "pullraptor-br18-maintenance-rehearsal/1", "acceptance": "pending_independent_review",
               "scope": "owned Python 3.12 CLI beta fixtures; no publication, target execution or atomic-update claim",
               "source_revision": BASE_REVISION, "harness_sha256": digest(__file__), "installer_helper_sha256": digest(HELPER),
               "runtime": {"python": platform.python_version(), "implementation": platform.python_implementation(),
                           "platform": platform.system(), "machine": platform.machine(), "python_executable_sha256": digest(sys.executable)},
               "tools": ledger, "scenarios": {}, "network_boundary": "pip --no-index; host OS egress enforcement recorded by coordinator"}
    with tempfile.TemporaryDirectory(prefix="pullraptor-br18-") as tmp:
        root = Path(tmp)
        root.chmod(0o700)
        run = Runner(root)
        try:
            receipt["workspace_revision"] = run.run(["git", "-C", source, "rev-parse", "HEAD"]).stdout.strip()
            receipt["git_runtime"] = {"version": run.run(["git", "--version"]).stdout.strip(),
                                      "executable_sha256": digest(shutil.which("git", path=run.env["PATH"]))}
            receipt["document_digests"] = {name: digest(source / name) for name in
                ("docs/superpowers/plans/2026-10-05-acceptance-maintenance-closure.md", "docs/worker-dispatch.md",
                 "docs/releases/beta-0.1-maintenance.md", "docs/security-architecture.md", "docs/mathematical-core.md", "docs/evaluation.md")}
            if candidate is None:
                candidate = prepare_candidate(source, output / "candidate", wheelhouse, run)
            candidate = Path(candidate).resolve()
            provenance_path = candidate.parent / "candidate-provenance.json"
            provenance = json.loads(provenance_path.read_text())
            verify_candidate_source(source, candidate, provenance, run)
            if provenance["trusted_base"] != BASE_REVISION or provenance["public_release"] is not False or provenance["wheel_sha256"] != digest(candidate):
                raise AssertionError("candidate provenance mismatch")
            if digest(candidate.parent / "candidate-source.tar") != provenance["source_archive_sha256"]:
                raise AssertionError("candidate committed source digest mismatch")
            receipt["candidate"] = {**wheel_identity(candidate, CANDIDATE_VERSION), "provenance": provenance}
            receipt["prior"] = wheel_identity(prior, "0.1.0b1")
            review = review_fixture(run)
            receipt["review_fixture"] = {"base": review[1], "head": review[2], "source_files": {p.name: digest(p) for p in review[0].glob("*") if p.is_file()}}
            for name in ("successful_update", "after_old_dist_info_removal", "after_first_package_write"):
                venv = root / name
                python = new_venv(run, venv, wheelhouse)
                pip_install(run, python, prior)
                report = root / f"{name}-previous-report.json"
                baseline, canonical = verify_installed(run, venv, prior, "0.1.0b1", review, report)
                (output / f"{name}-baseline-report.json").write_bytes(canonical)
                if name == "successful_update":
                    corrupt_dir = root / "corrupt"
                    corrupt_dir.mkdir()
                    corrupt = corrupt_dir / candidate.name
                    corrupt.write_bytes(candidate.read_bytes()[:128])
                    before = filesystem_state(venv)
                    refused = pip_install(run, python, corrupt, expected=None)
                    after = filesystem_state(venv)
                    if refused.returncode == 0 or before != after:
                        raise AssertionError("corrupt candidate changed baseline installation")
                    receipt["scenarios"]["corrupt_candidate"] = {"exit_code": refused.returncode, "before": before, "after": after, "candidate_sha256": digest(corrupt)}
                    pip_install(run, python, candidate)
                    verified, _ = verify_installed(run, venv, candidate, CANDIDATE_VERSION, review, report, canonical)
                    receipt["scenarios"][name] = {"baseline": baseline, "verified": verified, "uninstall": uninstall(run, venv, report, canonical)}
                    continue
                scenario = interrupt_update(run, venv, candidate, name)
                scenario["baseline"] = baseline
                scenario["operator_removed_stashes"] = repair_orphans(run, venv)
                pip_install(run, python, prior, force=True)
                scenario["recovered"], _ = verify_installed(run, venv, prior, "0.1.0b1", review, report, canonical)
                pip_install(run, python, candidate)
                scenario["retry"], _ = verify_installed(run, venv, candidate, CANDIDATE_VERSION, review, report, canonical)
                pip_install(run, python, prior, force=True)
                scenario["rollback"], _ = verify_installed(run, venv, prior, "0.1.0b1", review, report, canonical)
                scenario["uninstall"] = uninstall(run, venv, report, canonical)
                receipt["scenarios"][name] = scenario
            receipt["result"] = "development_verified"
        except Exception as error:
            receipt["result"] = "failed"
            receipt["failure"] = f"{type(error).__name__}: {error}"
            raise
        finally:
            receipt["commands"] = run.commands
            receipt["environment_keys"] = sorted(run.env)
            write_json(output / "receipt.json", receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--wheelhouse", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, help="existing private fixture wheel with adjacent provenance/source archive")
    parser.add_argument("--prepare-candidate", type=Path, help="build only into this fixture directory, without an installation rehearsal")
    args = parser.parse_args()
    if args.prepare_candidate:
        args.output.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="pullraptor-br18-build-") as tmp:
            run = Runner(Path(tmp))
            candidate = prepare_candidate(args.source.resolve(), args.prepare_candidate.resolve(), args.wheelhouse.resolve(), run)
            write_json(args.output / "candidate-build-commands.json", run.commands)
        print(candidate)
    else:
        receipt = run_rehearsal(args.source, args.output, args.wheelhouse, args.candidate)
        print(json.dumps({"result": receipt["result"], "receipt": str(args.output / "receipt.json")}, sort_keys=True))


if __name__ == "__main__":
    main()
