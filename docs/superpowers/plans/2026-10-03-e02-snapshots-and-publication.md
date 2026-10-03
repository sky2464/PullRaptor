# E02: Immutable local snapshots and trusted PR publication Implementation Plan

**Build handoff:** [task board](../../build-task-board.md), [exact task cards](../../build-tasks.json) and [coordinator interface decisions](../../build-interfaces.md). Read these with this plan; distinguish reviewed-output construction prerequisites from activation/acceptance gates.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish local snapshot integrity and the separate, revision-bound GitHub CI publisher.

**Architecture:** Keep filesystem capture, coordinator review, platform authorization and publication separate. Add frozen LocalSnapshot(tree_oid, base_tip, manifest_digest, capture_mode, include_untracked, discovery_complete, diagnostics) and PublicationContext(repository_id, pr_number, workflow_id, run_id, artifact_digest, reviewer_digest, head, base_tip, comparison_base, policy_digest, scope_digest). The connector independently derives this context; report fields cannot grant publication authority. Stable obligation keys and revision observations remain separate.

**Tech Stack:** Python 3.12 stdlib, existing Git/process/report modules, unittest; isolated CI and GitHub REST adapter outside the kernel.

**Spec:** [E02 child specification](../specs/2026-10-03-e02-snapshots-and-publication.md).

**Status:** Partial implementation: local capture and publication contract/lifecycle helpers exist at the assigned base (PR 16). Checked steps preserve that work; publisher integration, full report/context binding, CLI/MCP consumer parity and Task 4 actual CI/pilot evidence remain incomplete. No E02 criterion is accepted by the checkboxes. Read the spec and [execution gate](../../planning-contract.md) before starting. Existing artifacts are inputs to audit, not accepted implementations of the expanded scope.

## Global Constraints

- Zero third-party packages in the deterministic kernel; Git executable required.
- Python 3.12.x pinned baseline; versions 3.13+ / 3.14+ admitted only after AST parser parity verification.
- Keep competing product names out of all project files.
- Apply the [execution and acceptance contract](../../planning-contract.md); these are proposed tasks, not execution authorization.
- Trusted base policy and coordinator-owned scope are authoritative; unknown/incomplete/conflicted/stale results stay visible.
- Never execute reviewed code in the analysis process; optional execution requires the separately accepted E06 runner.
- No ambient worker credentials, foreign/shared caches, automatic dependency installation or automatic merge.

## Review Focus

1. Concurrent edits/index changes must produce a capture-race failure, not a mixed snapshot (Task 1).
2. Head policy edits and unchanged-head/base-policy drift cannot authorize publication (Task 2).
3. Same-head cross-PR/workflow artifact replay must be denied (Task 2).
4. A timed-out POST may already exist; reconcile bot-owned records before retrying (Task 3).
5. Fork input cannot read publisher credentials or execute Git filters in capture (Tasks 1 and 4).

## File and interface map

- Task 1: modify `src/pullraptor/git_snapshot.py`, `src/pullraptor/__main__.py`; create `src/pullraptor/local_snapshot.py`; race-aware bounded capture.
- Task 2: modify `src/pullraptor/publisher.py`; create `src/pullraptor/publication_contract.py`; authorization and location validation.
- Task 3: modify `src/pullraptor/publisher.py`; create `src/pullraptor/publication_lifecycle.py`; stable observations and duplicate-safe writes.
- Task 4: create `integrations/github/review.yml`, `docs/ci-review.md`, `tests/test_ci_template.py`; separate analysis and publisher deployment.

### Task 1: Capture immutable local content without repository execution

**Acceptance:** E02-A1.

**Files:** modify `src/pullraptor/git_snapshot.py`, `src/pullraptor/__main__.py`; create `src/pullraptor/local_snapshot.py`; test: `tests/test_local_snapshot.py`.

**Interfaces:**
- Consumes: existing Limits, Deadline, Snapshot and safe Git/process helpers.
- Produces: `capture_local(repo: Path, base_tip: str, *, staged_only: bool, include_untracked: bool, limits: Limits, deadline: Deadline) -> LocalSnapshot`, with the record fields defined in the spec.

- [x] **Step 1: Write the failing acceptance tests.** Add `test_filter_sentinel_never_runs`, `test_capture_race_incomplete`, `test_untracked_default_excluded`, `test_untracked_explicit_opt_in`, `test_worktree_index_and_refs_unchanged`, and `test_worktree_gitdir_file_supported`. For a concurrent byte/index change, return cause `capture_race` and discovery_complete false; for stable input, materialize exact admitted bytes and modes without Git add/clean filters.

Expected assertions for the stated adverse fixture:

```python
assert result.discovery_complete is False
assert "capture_race" in result.diagnostics
assert sentinel.exists() is False
```

- [x] **Step 2: Run the focused suite and confirm a meaningful failure.** Run `PYTHONPATH=src python3.12 -m unittest tests.test_local_snapshot tests.test_working_tree -v`. Missing new interfaces may fail import initially; existing code must fail the new adverse assertion before correction.
- [x] **Step 3: Implement the declared interfaces.** Read admitted files through no-follow bounded descriptors, compare metadata/content identities before sealing, and create blobs/trees through fixed safe plumbing with temporary operator-owned storage. Do not use repository `git add --all`; handle linked worktree metadata through trusted Git admission, not `.git/index` assumptions. Unsupported symlink/submodule/non-UTF-8 entries stay in diagnostics. Wire the explicit untracked flag into CLI/MCP later.
- [x] **Step 4: Run the same suite.** Require all named assertions to pass, including the successful fixture; retain raw outputs and exact input/tool identities.
- [x] **Step 5: Commit the reviewed task on an allowed feature branch.** Stage only this task's files; use commit message `feat: capture bounded immutable local snapshots`. Do not commit to `main`.

### Task 2: Independently bind publication to platform and base policy

**Acceptance:** E02-A2.

**Files:** modify `src/pullraptor/publisher.py`; create `src/pullraptor/publication_contract.py`; test: `tests/test_publication_contract.py`.

**Interfaces:**
- Consumes: bounded Report and independently acquired PublicationContext.
- Produces: `validate_publication(report: Report, expected: PublicationContext, current: PublicationContext) -> PublicationDecision`; frozen PublicationDecision(authorized: bool, cause: str, inline_keys: tuple[str, ...]).

- [x] **Step 1: Write the failing acceptance tests.** Add `test_base_policy_changed_same_head`, `test_cross_pr_replay`, `test_wrong_workflow_run_artifact`, `test_missing_or_prefix_head_denied`, `test_deleted_side_location`, `test_limit_failure_no_inline`, and `test_current_exact_context_authorized`. The changed-policy fixture has identical head and differing policy digest; authorization must be false with cause `stale_policy`.

Expected assertions for the stated adverse fixture:

```python
assert decision.authorized is False
assert decision.cause == "stale_policy"
assert decision.inline_keys == ()
```

- [x] **Step 2: Run the focused suite and confirm a meaningful failure.** Run `PYTHONPATH=src python3.12 -m unittest tests.test_publication_contract tests.test_publisher -v`. Missing new interfaces may fail import initially; existing code must fail the new adverse assertion before correction.
- [x] **Step 3: Implement the declared interfaces.** Require exact immutable identities, authoritative artifact origin, complete applicable receipts and valid side-aware locations. Compare base tip/comparison base/policy/scope/reviewer as well as head. Use the owned renderer rather than interpolating untrusted finding text. Keep publish preview read-only.
- [x] **Step 4: Run the same suite.** Require all named assertions to pass, including the successful fixture; retain raw outputs and exact input/tool identities.
- [x] **Step 5: Commit the reviewed task on an allowed feature branch.** Stage only this task's files; use commit message `feat: bind publication to trusted review context`. Do not commit to `main`.

### Task 3: Reconcile comment lifecycle and bounded retries

**Acceptance:** E02-A3.

**Files:** modify `src/pullraptor/publisher.py`; create `src/pullraptor/publication_lifecycle.py`; test: `tests/test_publication_lifecycle.py`.

**Interfaces:**
- Consumes: authorized PublicationDecision, PublicationContext, pinned report and connector-owned comment inventory.
- Produces: `plan_publication(context: PublicationContext, report: Report, existing: tuple[PublishedObservation, ...]) -> PublicationPlan`; frozen PublishedObservation(owner_id, platform_id, obligation_key, observation_id, witness_digest, dismissed) and PublicationPlan(create, update, outdated, deferred), each a tuple of observation IDs.

- [x] **Step 1: Write the failing acceptance tests.** Add `test_duplicate_delivery_no_second_comment`, `test_post_timeout_reconcile_owner`, `test_foreign_marker_not_updated`, `test_changed_witness_renews_review`, `test_dismissal_not_resolution`, and `test_ten_inline_cap_full_summary`. After a successful POST with lost response, a reconciled bot-owned observation yields an empty create tuple.

Expected assertions for the stated adverse fixture:

```python
assert plan.create == ()
assert foreign_comment_id not in plan.update
```

- [x] **Step 2: Run the focused suite and confirm a meaningful failure.** Run `PYTHONPATH=src python3.12 -m unittest tests.test_publication_lifecycle tests.test_publisher -v`. Missing new interfaces may fail import initially; existing code must fail the new adverse assertion before correction.
- [x] **Step 3: Implement the declared interfaces.** Authenticate bot ownership, paginate bounded inventory, reconcile ambiguous writes before retry, preserve independent dismissal/evidence states, and cap inline output without dropping report findings. Use at most 3 attempts in one 30-second deadline; expose remaining unpublished entries.
- [x] **Step 4: Run the same suite.** Require all named assertions to pass, including the successful fixture; retain raw outputs and exact input/tool identities.
- [x] **Step 5: Commit the reviewed task on an allowed feature branch.** Stage only this task's files; use commit message `feat: reconcile revision-bound review comments`. Do not commit to `main`.

### Task 4: Ship and exercise the hostile CI template

**Acceptance:** E02-A4.

**Files:** create `integrations/github/review.yml`, `docs/ci-review.md`, `tests/test_ci_template.py`; test: `tests/test_ci_template.py`.

**Interfaces:**
- Consumes: accepted E07 artifact, E01 report and Tasks 2–3 publisher.
- Produces: declarative analysis/publisher job contract and saved actual-enforcement receipts; no new kernel interface.

- [x] **Step 1: Write the failing acceptance tests.** Add `test_actions_full_digest_pinned`, `test_checkout_credentials_not_persisted`, `test_pr_text_only_env_data`, `test_publisher_no_head_checkout_or_cache`, and `test_missing_isolation_refuses_hostile_profile`. In the enforcement fixture where egress denial is unavailable, admission must be `unavailable`; credential and filter sentinels must remain unread/unexecuted.

Expected assertions for the stated adverse fixture:

```python
assert admission == "unavailable"
assert publisher_secret_seen_by_analysis is False
```

- [x] **Step 2: Run the focused suite and confirm a meaningful failure.** Run `PYTHONPATH=src python3.12 -m unittest tests.test_ci_template -v`. Missing new interfaces may fail import initially; existing code must fail the new adverse assertion before correction.
- [x] **Step 3: Implement the declared interfaces.** Install a trusted artifact outside head content. Prepare exact Git objects separately, strip acquisition credentials, deny analysis egress and enforce read-only source/resource isolation. Publisher fetches only bounded authenticated report artifacts, independently validates origins and fresh metadata, and never checks out head. Do not repurpose the current development test workflow as hostile-review evidence.
- [ ] **Step 4: Run the same suite.** Require all named assertions to pass, including the successful fixture; retain raw outputs and exact input/tool identities. Run same-repository and fork pilots through the accepted deployment boundary; save enforcement, artifact and platform receipts before accepting E02B.
- [x] **Step 5: Commit the reviewed task on an allowed feature branch.** Stage only this task's files; use commit message `feat: add isolated review and publication template`. Do not commit to `main`.

## Package acceptance and handoff

- [ ] Re-run this package's focused suites and the affected existing suites in the trusted development environment; reviewed-source execution uses only an accepted runner.
- [ ] Exercise the scoped install/connect → exact review → visible coverage → repeat after changes → revoke/uninstall flow where this package exposes a delivery surface.
- [ ] Record all E02-A1 through E02-A4 criteria, dependency/license inventory and actual resource measurements in `docs/acceptance/E02.md`.
- [ ] Obtain independent acceptance review. Until then retain the actual implementation state and acceptance pending in the master plan. Accepted subsets do not mark the broader package complete.
