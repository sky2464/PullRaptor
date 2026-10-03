# E06: Patch receipts, isolated regression runner and reviewed preferences Implementation Plan

**Build handoff:** [task board](../../build-task-board.md), [exact task cards](../../build-tasks.json) and [coordinator interface decisions](../../build-interfaces.md). Read these with this plan; distinguish reviewed-output construction prerequisites from activation/acceptance gates.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver scoped draft patches with truthful independent validation and explicit preference approval.

**Architecture:** Add frozen PatchProposal(head, digest, allowed_paths, edits), PathEdit(path, old_blob, old_mode, new_bytes), ValidationReceipt(patch_digest, original_tree, result_tree, stages, obligation_results, execution), and StageResult(stage, status, cause). P0 preconditions, P1 exact application, P2 parse, P3 re-analysis, P4 actual isolated checks are distinct. RunnerPlan(image_digest, argv, input_tree, resource_limits, network_policy) comes only from trusted configuration. PreferenceProposal(author, source_report, scope, declarative_changes) is separate from AcceptedPreference(approver, policy_revision, proposal_digest).

**Tech Stack:** Python 3.12 stdlib/unittest; independently enforced OS/container runner outside the kernel; declarative JSON/TOML contracts.

**Spec:** [E06 child specification](../specs/2026-10-03-e06-patches-runner-preferences.md).

**Status:** Proposed; all tasks below are unexecuted. Read the spec and [execution gate](../../planning-contract.md) before starting. Existing artifacts are inputs to audit, not accepted implementations of the expanded scope.

## Global Constraints

- Zero third-party packages in the deterministic kernel; Git executable required.
- Python 3.12.x pinned baseline; versions 3.13+ / 3.14+ admitted only after AST parser parity verification.
- Keep competing product names out of all project files.
- Apply the [execution and acceptance contract](../../planning-contract.md); these are proposed tasks, not execution authorization.
- Trusted base policy and coordinator-owned scope are authoritative; unknown/incomplete/conflicted/stale results stay visible.
- Never execute reviewed code in the analysis process; optional execution requires the separately accepted E06 runner.
- No ambient worker credentials, foreign/shared caches, automatic dependency installation or automatic merge.

## Review Focus

1. Changed head or mismatched old mode/blob invalidates patch preconditions (Task 1).
2. Traversal/symlink/policy changes cannot escape allowed text paths (Task 1).
3. No runner or cancelled/timeout execution stays not_run/failed, never verified (Task 2).
4. Passing unrelated tests cannot clear an obligation or imply reproduced-and-resolved (Task 3).
5. Feedback/model text cannot approve a preference or weaken base policy (Task 4).

## File and interface map

- Task 1: create `src/pullraptor/patches.py`; draft contract and immutable tree application.
- Task 2: create `src/pullraptor/runner_contract.py`, `runner/launcher.py`, `runner/profile.json`; trusted launch contract and actual execution receipts.
- Task 3: create `src/pullraptor/patch_validation.py`; modify `src/pullraptor/render.py`; stage dependency and obligation-specific evidence.
- Task 4: create `src/pullraptor/preferences.py`; modify `src/pullraptor/config.py`; audited proposal and approver boundary.

### Task 1: Validate patch paths and apply exact preconditions

**Acceptance:** E06-A1.

**Files:** create `src/pullraptor/patches.py`; test: `tests/test_patches.py`.

**Interfaces:**
- Consumes: PatchProposal, trusted allowed-path set, exact head Snapshot and bounded blob access.
- Produces: `validate_patch(proposal: PatchProposal, head: Snapshot) -> tuple[StageResult, ...]`; `apply_patch_tree(proposal: PatchProposal, head: Snapshot) -> PatchedTree`; PatchedTree(original_tree, result_tree, patch_digest, stages).

- [ ] **Step 1: Write the failing acceptance tests.** Add `test_old_blob_mode_mismatch`, `test_stale_head`, `test_traversal_symlink_and_submodule_denied`, `test_workflow_policy_path_denied`, `test_exact_no_fuzz_application`, and `test_rename_delete_not_admitted`. For changed head, P0 is stale and P1 is not_run; the developer worktree is unchanged.

Expected assertions for the stated adverse fixture:

```python
assert stages["P0"].status == "stale"
assert stages["P1"].status == "not_run"
assert working_tree_after == working_tree_before
```

- [ ] **Step 2: Run the focused suite and confirm a meaningful failure.** Run `PYTHONPATH=src python3.12 -m unittest tests.test_patches -v`. Missing new interfaces may fail import initially; existing code must fail the new adverse assertion before correction.
- [ ] **Step 3: Implement the declared interfaces.** Use immutable blobs/tree construction in private scratch storage; preserve exact context and modes and reject fuzz or unsupported operations. Parse proposal data with strict decoder; model-generated allowed paths cannot grant permission. Apply no repository hooks/filters or generated commands.
- [ ] **Step 4: Run the same suite.** Require all named assertions to pass, including the successful fixture; retain raw outputs and exact input/tool identities.
- [ ] **Step 5: Commit the reviewed task on an allowed feature branch.** Stage only this task's files; use commit message `feat: validate exact scoped patch preconditions`. Do not commit to `main`.

### Task 2: Enforce a separate execution boundary

**Acceptance:** E06-A2.

**Files:** create `src/pullraptor/runner_contract.py`, `runner/launcher.py`, `runner/profile.json`; test: `tests/test_runner_boundary.py`.

**Interfaces:**
- Consumes: Task 1 PatchedTree and trusted RunnerPlan; source commands never enter the analysis process.
- Produces: `validate_runner(plan: RunnerPlan, controls: IsolationControls) -> RunnerAdmission`; IsolationControls(filesystem, egress, credentials, process_tree, cpu, memory, pids), RunnerAdmission(allowed, cause); launcher `execute(plan: RunnerPlan) -> ExecutionReceipt` with image/runtime/input/argv/result/limits/termination identities.

**Bootstrap boundary:** Before E06-A2 acceptance, only independently reviewed synthetic control fixtures may execute, inside a separately designed disposable evaluation boundary with denied credentials/egress and bounded filesystem/process/resources. They establish whether the runner enforces its controls; they are not reviewed target-repository tests. Reviewed target code remains denied until independent runner acceptance. Missing evaluation controls block these fixtures, never justify host execution.

- [ ] **Step 1: Write the failing acceptance tests.** Add `test_missing_egress_or_filesystem_control_refuses`, `test_no_ambient_credentials_or_host_socket`, `test_timeout_kills_process_tree`, `test_output_flood_bounded`, and `test_no_runner_not_run`. A missing filesystem control returns allowed false and cause `isolation_unavailable`; do not execute a harmless fallback on the host.

Expected assertions for the stated adverse fixture:

```python
assert admission.allowed is False
assert admission.cause == "isolation_unavailable"
assert host_execution_count == 0
```

- [ ] **Step 2: Run the focused suite and confirm a meaningful failure.** Run `PYTHONPATH=src python3.12 -m unittest tests.test_runner_boundary -v`. Missing new interfaces may fail import initially; existing code must fail the new adverse assertion before correction.
- [ ] **Step 3: Implement the declared interfaces.** Design and review the actual OS enforcement before execution. Mount only immutable required source read-only and bounded private scratch, deny network and inherited secrets/handles, enforce image digest and resource limits, and kill/reap process descendants. Record unsupported controls and refuse admission; environment filtering alone is insufficient.
- [ ] **Step 4: Run the same suite.** Require all named assertions to pass, including the successful fixture; retain raw outputs and exact input/tool identities. Acceptance requires escape/credential/output/deadline fixtures inside the declared deployment boundary, not only mocked launch tests.
- [ ] **Step 5: Commit the reviewed task on an allowed feature branch.** Stage only this task's files; use commit message `feat: add isolated regression execution receipts`. Do not commit to `main`.

### Task 3: Re-analyze obligations and retain P0–P4 states

**Acceptance:** E06-A3.

**Files:** create `src/pullraptor/patch_validation.py`; modify `src/pullraptor/render.py`; test: `tests/test_patch_validation.py`.

**Interfaces:**
- Consumes: Task 1 PatchedTree, Task 2 ExecutionReceipt, same pinned ReviewContract and applicable accepted analyzers.
- Produces: `validate_correction(original: Report, patched: Report, patch: PatchedTree, execution: ExecutionReceipt | None) -> ValidationReceipt`; obligation_results includes obligation ID, exact checked predicate and outcome.

- [ ] **Step 1: Write the failing acceptance tests.** Add `test_parse_failure_skips_reanalysis`, `test_unrelated_pass_cannot_clear`, `test_reproduced_baseline_failure_then_patch_pass`, `test_no_reproduction_only_checks_passed`, `test_stale_receipt_after_push`, and `test_clean_reanalysis_equals_incremental`. A retained obligation with unrelated passing tests stays open; missing runner leaves P4 not_run.

Expected assertions for the stated adverse fixture:

```python
assert receipt.obligation_results[obligation_id].outcome == "open"
assert receipt.stages["P4"].status == "not_run"
```

- [ ] **Step 2: Run the focused suite and confirm a meaningful failure.** Run `PYTHONPATH=src python3.12 -m unittest tests.test_patch_validation tests.test_render -v`. Missing new interfaces may fail import initially; existing code must fail the new adverse assertion before correction.
- [ ] **Step 3: Implement the declared interfaces.** Validate actual receipts rather than proposal labels. Parse/re-review original and patched immutable trees under identical policies; preserve unknown alignment. Set reproduction status only for the same pinned relevant command failing baseline and passing patched. Render all stages, failures and missing checks without aggregate certainty claims.
- [ ] **Step 4: Run the same suite.** Require all named assertions to pass, including the successful fixture; retain raw outputs and exact input/tool identities.
- [ ] **Step 5: Commit the reviewed task on an allowed feature branch.** Stage only this task's files; use commit message `feat: retain independent patch validation stages`. Do not commit to `main`.

### Task 4: Approve preferences through trusted declarative policy

**Acceptance:** E06-A4.

**Files:** create `src/pullraptor/preferences.py`; modify `src/pullraptor/config.py`; test: `tests/test_preferences.py`.

**Interfaces:**
- Consumes: PreferenceProposal and explicitly authenticated maintainer/policy authority.
- Produces: `accept_preference(proposal: PreferenceProposal, *, approver: str, policy_revision: str, allowed_keys: frozenset[str]) -> AcceptedPreference`; changes permit presentation ordering and advisory display only in initial schema.

- [ ] **Step 1: Write the failing acceptance tests.** Add `test_model_cannot_self_approve`, `test_dismissal_not_policy_change`, `test_ci_scope_threshold_cannot_weaken`, `test_wrong_repo_scope_denied`, and `test_accepted_preference_audited`. Attempting to change required_scope or blocker thresholds is rejected even with a suggested maintainer name in source.

Expected assertions for the stated adverse fixture:

```python
assert policy_after == policy_before
assert rejection_cause == "protected_policy_key"
```

- [ ] **Step 2: Run the focused suite and confirm a meaningful failure.** Run `PYTHONPATH=src python3.12 -m unittest tests.test_preferences tests.test_config -v`. Missing new interfaces may fail import initially; existing code must fail the new adverse assertion before correction.
- [ ] **Step 3: Implement the declared interfaces.** Reject executable or unknown preference fields; require trusted approval provenance independent of comments/model output. Store source report/scope/approver and old/new policy digests. Keep accepted local presentation changes separate from base-owned CI policy and measure repeat-comment usefulness, not correctness.
- [ ] **Step 4: Run the same suite.** Require all named assertions to pass, including the successful fixture; retain raw outputs and exact input/tool identities.
- [ ] **Step 5: Commit the reviewed task on an allowed feature branch.** Stage only this task's files; use commit message `feat: require reviewed declarative preferences`. Do not commit to `main`.

## Package acceptance and handoff

- [ ] Re-run this package's focused suites and the affected existing suites in the trusted development environment; reviewed-source execution uses only an accepted runner.
- [ ] Exercise the scoped install/connect → exact review → visible coverage → repeat after changes → revoke/uninstall flow where this package exposes a delivery surface.
- [ ] Record all E06-A1 through E06-A4 criteria, dependency/license inventory and actual resource measurements in `docs/acceptance/E06.md`.
- [ ] Obtain independent acceptance review. Until then retain the actual implementation state and acceptance pending in the master plan. Accepted subsets do not mark the broader package complete.
