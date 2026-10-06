# BR18 development evidence

Scope: owned Python 3.12 beta CLI fixtures, trusted base `48bef09d985fbeb42749d1cc6238c74429616a25`, accepted b1 SHA-256 `d44d6da0e6fc667a26260896cd5f4d82c35b59f8126e65ce38d92d9a8e97be24`, distinct unpublished b2.dev0 fixture. Independent BR18 review is pending. This evidence does not authorize a release, customer updater or atomic updating claim.

Run the real installation rehearsal:

```sh
python3.12 scripts/maintenance_rehearsal.py --source . \
  --output docs/acceptance/artifacts/E07/maintenance/macos-arm64 \
  --wheelhouse .superpowers/sdd/acceptance-maintenance-closure/wheelhouse \
  --candidate tests/fixtures/e07/maintenance/pullraptor-0.1.0b2.dev0-py3-none-any.whl
```

Use `--output .../linux-x86_64` for the coordinator's Linux run. The owned disposable fixture location needs an executable mount for installed console scripts. On macOS the harness uses offline pip flags and a credential-free allowlist; it does not claim OS-enforced egress denial. The coordinator records the Linux container's actual network/filesystem/resource controls separately.

`macos-arm64/receipt.json` contains commands, exit codes, raw stdout/stderr, source/document/runtime/tool identities, installed file maps, entrypoint identities, checkpoint observations and each post-recovery verification. Baseline reports include a supported PY001 advisory and an explicit unresolved Python context coverage gap. The same canonical report is verified after successful update, b1 recovery, retry, rollback, and retained on actual uninstall.

The test-only helper wraps pinned pip's real `UninstallPathSet.remove` and `ZipBackedFile.save`; their reviewed function SHA-256 values are checked before installation. It blocks only after the original function performed its filesystem operation. The parent waits for an fsynced checkpoint record, inspects the actual installed filesystem, then sends SIGKILL to the installer's process group and reaps it. No elapsed delay selects the interruption. The two required states are: old metadata removed with zero replacement package files; exactly the first replacement package file (`__init__.py`) written with neither old nor candidate metadata present. Both interrupted states are explicitly incomplete.

Recovery is an operator procedure: record and delete only pip's known private uninstall stashes, reinstall pinned b1 through real pip, verify all wheel files and distribution/entrypoint identities, retry the candidate, roll back to b1, and uninstall through real pip. It preserves the previous report and verifies all seven beta exclusions (publisher and MCP scripts; staged, workdir, untracked, CLI MCP, AI flags). The uninstall credential scan is limited to the recorded credential basenames in the owned venv; no ambient credentials are passed.

`red-missing-harness.txt` records three initial failures when the real BR18 harness did not exist. `red-disabled-checkpoint/receipt.json` records a stronger adverse run with checkpoint signaling disabled only in a temporary copy of the helper: the actual installer exits successfully but the harness refuses to claim an interruption. `red-disabled-checkpoint/mutation.json` describes that mutation. `green-focused-tests.txt` and `focused-test-receipt.json` record the restored focused suite. No implementer acceptance decision is included.

Focused verification:

```sh
env -i HOME=/tmp/pullraptor-br18-test-home PATH=/opt/homebrew/bin:/usr/bin:/bin \
  PYTHONPATH=src \
  PULLRAPTOR_BR18_WHEELHOUSE="$PWD/.superpowers/sdd/acceptance-maintenance-closure/wheelhouse" \
  python3.12 -m unittest tests.test_update_recovery \
  tests.test_installed_artifacts.TestInstalledArtifacts.test_install_interrupt_recovery \
  tests.test_installed_artifacts.TestInstalledArtifacts.test_uninstall_no_credentials_remnants \
  tests.test_installed_artifacts.TestInstalledArtifacts.test_br18_prior_wheel_reinstall_rollback \
  tests.test_installed_artifacts.TestInstalledArtifacts.test_update_rollback_prior_accepted_artifact -v
```

The coordinator owns the broader project regression run and Linux verification, final source repinning, independent review, and integration gates. Broader E07/container/first-install criteria are outside this BR18 subset.
