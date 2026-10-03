# E09: Azure Repos and Pipelines integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect Azure Repos Git reviews with iteration-bound feedback and trusted pipeline policy.

**Architecture:** Add AzureReviewContext(organization_id, project_id, repository_id, pr_id, iteration_id, source_head, target_tip, comparison_base, policy_digest, scope_digest, reviewer_digest) independently acquired from the platform. Event payloads trigger authorized reacquisition rather than granting repo/ref authority. Separate acquisition, credential-free analysis and bounded comment/status publication. Extend the platform-neutral publication context with an explicit platform discriminator.

**Tech Stack:** Python stdlib connector and unittest; declarative Pipelines YAML/task/extension manifests; platform API outside the kernel.

**Spec:** [E09 child specification](../specs/2026-10-03-e09-azure-devops.md).

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

1. Same head on another PR/iteration cannot replay feedback (Task 1).
2. Target policy changes while source head stays fixed require re-analysis (Task 1).
3. Duplicated/reordered service hooks and lost writes need reconciliation (Task 2).
4. PR strings cannot become shell fragments or task configuration (Task 3).
5. Revoked/expired or wrong-organization credentials deny work and retain explicit failure (Tasks 1 and 3).

## File and interface map

- Task 1: create `src/pullraptor/azure_connector.py`; scoped platform acquisition.
- Task 2: create `src/pullraptor/azure_publisher.py`, `src/pullraptor/azure_events.py`; retry-safe bounded publication.
- Task 3: create `integrations/azure/task.json`, `integrations/azure/review.yml`, `integrations/azure/extension.json`, `docs/azure-install.md`; installable integration and policy mapping.

### Task 1: Authorize repositories and immutable PR iterations

**Acceptance:** E09-A1.

**Files:** create `src/pullraptor/azure_connector.py`; test: `tests/test_azure_connector.py`.

**Interfaces:**
- Consumes: trusted organization/repository allowlist, scoped connector credentials and E02 publication records.
- Produces: `resolve_azure_review(pr_id: int, *, connector: AzureConnectorPolicy) -> AzureReviewContext`; AzureConnectorPolicy(organization_id, allowed_repository_ids, api_version, transport_policy).

- [ ] **Step 1: Write the failing acceptance tests.** Add `test_wrong_org_repository_denied`, `test_iteration_exact_binding`, `test_same_head_target_policy_drift`, `test_expired_credentials_unavailable`, and `test_event_refs_not_authoritative`. Wrong organization returns denied without fetching source; target policy drift produces stale context.

Expected assertions for the stated adverse fixture:

```python
assert acquisition.status == "denied"
assert acquired_source_bytes == 0
```

- [ ] **Step 2: Run the focused suite and confirm a meaningful failure.** Run `PYTHONPATH=src python3.12 -m unittest tests.test_azure_connector -v`. Missing new interfaces may fail import initially; existing code must fail the new adverse assertion before correction.
- [ ] **Step 3: Implement the declared interfaces.** Authenticate scoped API acquisition, resolve exact source/target/iteration and trusted target-tip policy, and stage Git objects separately from analysis. Use approved transport/version, no arbitrary event URLs and no credential inheritance to workers.
- [ ] **Step 4: Run the same suite.** Require all named assertions to pass, including the successful fixture; retain raw outputs and exact input/tool identities.
- [ ] **Step 5: Commit the reviewed task on an allowed feature branch.** Stage only this task's files; use commit message `feat: authorize Azure review iterations`. Do not commit to `main`.

### Task 2: Map report lifecycle to comments and status

**Acceptance:** E09-A2.

**Files:** create `src/pullraptor/azure_publisher.py`, `src/pullraptor/azure_events.py`; test: `tests/test_azure_publication.py`.

**Interfaces:**
- Consumes: Task 1 context and E02 validated report/lifecycle planner.
- Produces: `publish_azure(report: Report, expected: AzureReviewContext, connector: AzureConnectorPolicy) -> AzurePublishReceipt`; AzurePublishReceipt(context, created, updated, deferred, status, cause).

- [ ] **Step 1: Write the failing acceptance tests.** Add `test_duplicate_reordered_hook`, `test_post_timeout_reconciles_owned_thread`, `test_stale_iteration_before_post`, `test_deleted_side_location`, `test_partial_review_not_success_status`, and `test_dismissal_not_refutation`. A required incomplete review cannot emit success; a duplicate delivery creates no second thread.

Expected assertions for the stated adverse fixture:

```python
assert receipt.status != "succeeded"
assert duplicate_receipt.created == ()
```

- [ ] **Step 2: Run the focused suite and confirm a meaningful failure.** Run `PYTHONPATH=src python3.12 -m unittest tests.test_azure_publication -v`. Missing new interfaces may fail import initially; existing code must fail the new adverse assertion before correction.
- [ ] **Step 3: Implement the declared interfaces.** Reacquire context immediately before each write, validate line/side/iteration mapping and bot ownership, and reconcile ambiguous outcomes with bounded pagination. Keep stable obligation keys separate from observations. Summaries preserve deferred findings and explicit partial/stale/publication-failed states.
- [ ] **Step 4: Run the same suite.** Require all named assertions to pass, including the successful fixture; retain raw outputs and exact input/tool identities.
- [ ] **Step 5: Commit the reviewed task on an allowed feature branch.** Stage only this task's files; use commit message `feat: publish iteration-bound Azure review feedback`. Do not commit to `main`.

### Task 3: Package and validate task, hooks and branch policy

**Acceptance:** E09-A3.

**Files:** create `integrations/azure/task.json`, `integrations/azure/review.yml`, `integrations/azure/extension.json`, `docs/azure-install.md`; test: `tests/test_azure_delivery.py`.

**Interfaces:**
- Consumes: E07 accepted artifact, Tasks 1–2 connector/publisher, trusted Pipelines runtime.
- Produces: pinned Services compatibility/install matrix, task/extension bundle and credential/isolation enforcement receipts.

- [ ] **Step 1: Write the failing acceptance tests.** Add `test_build_validation_policy_mapping`, `test_pr_strings_passed_as_data`, `test_fork_no_publish_secret`, `test_server_not_implicitly_supported`, and `test_uninstall_revokes_hooks_tokens`. Exercise install/connect/review/new iteration/revoke; after revocation no new job is accepted.

Expected assertions for the stated adverse fixture:

```python
assert jobs_after_revocation == 0
assert analysis_has_publish_credentials is False
assert untested_server_supported is False
```

- [ ] **Step 2: Run the focused suite and confirm a meaningful failure.** Run `PYTHONPATH=src python3.12 -m unittest tests.test_azure_delivery -v`. Missing new interfaces may fail import initially; existing code must fail the new adverse assertion before correction.
- [ ] **Step 3: Implement the declared interfaces.** Document minimal organization/project/repository scopes and branch-policy setup; pin API/task/bundle versions and license inventory. Provide preview publication and customer-CI mode with actual E02 isolation. Package a versioned extension without automatically publishing it.
- [ ] **Step 4: Run the same suite.** Require all named assertions to pass, including the successful fixture; retain raw outputs and exact input/tool identities. Run the flow against a test Services organization under authorized credentials; mocks alone cannot accept delivery or branch-policy mapping.
- [ ] **Step 5: Commit the reviewed task on an allowed feature branch.** Stage only this task's files; use commit message `feat: package Azure review integration`. Do not commit to `main`.

## Package acceptance and handoff

- [ ] Re-run this package's focused suites and the affected existing suites in the trusted development environment; reviewed-source execution uses only an accepted runner.
- [ ] Exercise the scoped install/connect → exact review → visible coverage → repeat after changes → revoke/uninstall flow where this package exposes a delivery surface.
- [ ] Record all E09-A1 through E09-A3 criteria, dependency/license inventory and actual resource measurements in `docs/acceptance/E09.md`.
- [ ] Obtain independent acceptance review. Until then retain the actual implementation state and acceptance pending in the master plan. Accepted subsets do not mark the broader package complete.
