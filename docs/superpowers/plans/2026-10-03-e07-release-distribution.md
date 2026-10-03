# E07: Packaged release, provenance and offline installation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Release independently verifiable CLI/container artifacts with clean installation and rollback evidence.

**Architecture:** Build only from an exact reviewed revision in a trusted build environment. Add ReleaseManifest(version, source_revision, artifacts, runtime_matrix, dependency_inventory, provenance_ref), ArtifactIdentity(kind, digest, size, entrypoints), and InstallReceipt(platform, runtime, artifact_digest, operation, result). Compare logical report output from source and installed artifacts; timestamps/build metadata are outside canonical analysis.

**Tech Stack:** Python stdlib and packaging tools in build-only environment; Git; pinned Linux container; unittest; no third-party runtime dependency in the kernel.

**Spec:** [E07 child specification](../specs/2026-10-03-e07-release-distribution.md).

**Status:** Partial Task 1 metadata implementation and suite evidence exist from PR 14; exact dependency/license admission and full E07 acceptance remain pending. Tasks 2–3 remain unexecuted. Read the spec and [execution gate](../../planning-contract.md) before starting. Existing artifacts are inputs to audit, not accepted implementations of the expanded scope.

## Global Constraints

- Zero third-party packages in the deterministic kernel; Git executable required.
- Python 3.12.x pinned baseline; versions 3.13+ / 3.14+ admitted only after AST parser parity verification.
- Keep competing product names out of all project files.
- Apply the [execution and acceptance contract](../../planning-contract.md); these are proposed tasks, not execution authorization.
- Trusted base policy and coordinator-owned scope are authoritative; unknown/incomplete/conflicted/stale results stay visible.
- Never execute reviewed code in the analysis process; optional execution requires the separately accepted E06 runner.
- No ambient worker credentials, foreign/shared caches, automatic dependency installation or automatic merge.

## Review Focus

1. Package metadata cannot imply untested Python-minor support (Task 1).
2. Mutable image tags or self-reported hashes cannot establish provenance (Task 2).
3. Installed and source reviews must yield identical completed canonical reports (Task 3).
4. Offline install/update rollback must work without source cloning (Task 3).
5. Image execution as non-root alone cannot claim hostile isolation or widen global Git trust (Tasks 1–2).

## File and interface map

- Task 1: modify `pyproject.toml`, `Dockerfile`, `README.md`; create `docs/distribution.md`; honest supported-runtime and install contracts.
- Task 2: create `release/build.py`, `release/manifest.schema.json`, `.github/workflows/release-candidate.yml`; modify `Dockerfile`; trusted build/provenance chain.
- Task 3: create `tests/test_installed_artifacts.py`, `release/install_matrix.json`, `docs/acceptance/E07.md`; artifact acceptance on every claimed platform.

### Task 1: Bound build metadata and customer entry points

**Acceptance:** E07-A1.

**Files:** modify `pyproject.toml`, `Dockerfile`, `README.md`; create `docs/distribution.md`; test: `tests/test_distribution_metadata.py`.

**Interfaces:**
- Consumes: E01 runtime contract and existing CLI/publisher/MCP entry points.
- Produces: wheel/source/container manifest declarations and exact supported runtime/profile matrix; no new kernel runtime imports.

- [x] **Step 1: Write the failing acceptance tests.** Add `test_python_minor_claim_matches_acceptance`, `test_no_runtime_dependencies`, `test_image_cli_default`, `test_no_global_safe_directory_wildcard`, and `test_customer_no_source_clone`. Untested Python minors must not be claimed by unconstrained metadata; released image defaults to CLI help/review, not running the repository test suite.

Expected assertions for the stated adverse fixture:

```python
assert admitted_python_minors == ("3.12",)
assert kernel_runtime_dependencies == ()
assert global_safe_directory_wildcard is False
```

- [x] **Step 2: Run the focused suite and confirm a meaningful failure.** Run `PYTHONPATH=src python3.12 -m unittest tests.test_distribution_metadata -v`. Missing new interfaces may fail import initially; existing code must fail the new adverse assertion before correction.
- [x] **Step 3: Implement the declared interfaces.** Align metadata/runtime checks to 3.12.x until parser parity is accepted. Separate development tests from runtime image, remove global trust widening, document scoped trusted mounts and executable prerequisites, and provide source-free installation commands for local/offline profiles.
- [x] **Step 4: Run the same suite.** Require all named assertions to pass, including the successful fixture; retain raw outputs and exact input/tool identities.
- [x] **Step 5: Commit the reviewed task on an allowed feature branch.** Stage only this task's files; use commit message `feat: define honest release installation contracts`. Do not commit to `main`. Evidence: included in `feat/e01-acceptance-e07-metadata` (2026-10-03); E07-A1 package acceptance record still pending.

### Task 2: Build pinned artifacts and verifiable release provenance

**Acceptance:** E07-A2.

**Files:** create `release/build.py`, `release/manifest.schema.json`, `.github/workflows/release-candidate.yml`; modify `Dockerfile`; test: `tests/test_release_provenance.py`.

**Interfaces:**
- Consumes: exact reviewed source revision and pinned trusted build/runtime inventories.
- Produces: `verify_release(manifest: ReleaseManifest, expected_revision: str, trusted_origin: BuildOrigin) -> ReleaseDecision`; BuildOrigin(workflow_digest, run_id, repository_id, artifact_digests), ReleaseDecision(admitted, cause).

- [ ] **Step 1: Write the failing acceptance tests.** Add `test_mutable_tag_insufficient`, `test_wrong_revision_or_build_origin`, `test_artifact_tampering`, `test_build_dependency_inventory`, and `test_two_builds_reported`. A digest supplied by the artifact alone cannot authenticate origin; wrong expected revision returns admitted false.

Expected assertions for the stated adverse fixture:

```python
assert decision.admitted is False
assert decision.cause == "wrong_source_revision"
```

- [ ] **Step 2: Run the focused suite and confirm a meaningful failure.** Run `PYTHONPATH=src python3.12 -m unittest tests.test_release_provenance -v`. Missing new interfaces may fail import initially; existing code must fail the new adverse assertion before correction.
- [ ] **Step 3: Implement the declared interfaces.** Pin container base/action commits/build dependencies, produce wheel/source/image identities and license/SBOM/provenance records from platform-derived trusted build metadata. Verify origin independently of manifest hashes. Compare two clean builds and report reproducibility deviations rather than promising byte identity without evidence. Keep release uploads behind their separately authorized release action.
- [ ] **Step 4: Run the same suite.** Require all named assertions to pass, including the successful fixture; retain raw outputs and exact input/tool identities.
- [ ] **Step 5: Commit the reviewed task on an allowed feature branch.** Stage only this task's files; use commit message `feat: produce pinned release candidate provenance`. Do not commit to `main`.

### Task 3: Prove clean-machine installation, equivalence and recovery

**Acceptance:** E07-A3.

**Files:** create `tests/test_installed_artifacts.py`, `release/install_matrix.json`, `docs/acceptance/E07.md`; test: `tests/test_installed_artifacts.py`.

**Interfaces:**
- Consumes: Task 2 verified ReleaseManifest/artifacts and licensed immutable review fixtures.
- Produces: InstallReceipt records and canonical comparisons for each admitted runtime/platform/artifact/profile.

- [ ] **Step 1: Write the failing acceptance tests.** Add `test_fresh_venv_without_repo_clone`, `test_offline_wheel_and_image`, `test_source_wheel_container_canonical_equal`, `test_uninstall_no_credentials_left`, `test_update_rollback_previous_report`, `test_interrupted_install_recovery`, and `test_first_install_without_prior_release`. Use a fixture producing both advisory findings and a required coverage gap; preserve both in installed reports. A first release has no previously accepted artifact: interrupted initial installation must leave a clean or explicit recoverable failure state. Update/rollback acceptance requires an independently accepted prior artifact fixture; when absent, retain that criterion as `not_run` and exclude update/rollback release claims until evidence exists. Never invent a prior acceptance marker.

Expected assertions for the stated adverse fixture:

```python
assert installed_canonical == source_canonical
assert customer_clone_required is False
# Update fixture only, with independent prior-artifact acceptance:
assert rollback_version == previously_accepted_version
# First-install fixture, with no accepted prior artifact:
assert initial_install_state in {"clean", "recoverable_failure"}
```

- [ ] **Step 2: Run the focused suite and confirm a meaningful failure.** Run `PYTHONPATH=src python3.12 -m unittest tests.test_installed_artifacts -v`. Missing new interfaces may fail import initially; existing code must fail the new adverse assertion before correction.
- [ ] **Step 3: Implement the declared interfaces.** Run trusted development/install checks in clean supported environments and accepted runtime boundaries, with network denied for offline cases. Record artifact and runtime sizes separately, install/startup/RSS, uninstall remnants and actual update/rollback steps. Do not run arbitrary reviewed build scripts during installation.
- [ ] **Step 4: Run the same suite.** Require all named assertions to pass, including the successful fixture; retain raw outputs and exact input/tool identities.
- [ ] **Step 5: Commit the reviewed task on an allowed feature branch.** Stage only this task's files; use commit message `test: verify release installation and rollback`. Do not commit to `main`.

Initial-install evidence may be recorded as a subset. If update/rollback lacks the required prior accepted artifact and remains `not_run`, E07-A3 and full E07 acceptance remain pending; do not mark the whole criterion passed or advertise update/rollback support.

## Package acceptance and handoff

- [ ] Re-run this package's focused suites and the affected existing suites in the trusted development environment; reviewed-source execution uses only an accepted runner.
- [ ] Exercise the scoped install/connect → exact review → visible coverage → repeat after changes → revoke/uninstall flow where this package exposes a delivery surface.
- [ ] Record all E07-A1 through E07-A3 criteria, dependency/license inventory and actual resource measurements in `docs/acceptance/E07.md`.
- [ ] Obtain independent acceptance review. Until then retain the actual implementation state and acceptance pending in the master plan. Accepted subsets do not mark the broader package complete.
