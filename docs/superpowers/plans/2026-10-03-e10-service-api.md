# E10: Versioned review service, SDK, app and deployments Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose the owned review contract through an authorized, recoverable service without expanding kernel authority.

**Architecture:** Keep service/API/SDK/connector code outside the kernel in service/ and sdk/. Add ServiceRequest(tenant_id, repository_id, base_tip, comparison_base, head_or_snapshot, policy_origin, scope, profile, reviewer_digest), AuthorizedJob(job_id, tenant_id, repository_id, request_digest, state), and CompletionEvent(event_id, tenant_id, job_id, report_digest, state, issued_at). Trusted service resolution independently authorizes identities and creates coordinator scope. Job states are queued/running/completed/cancelled/failed/expired; completed means a report was stored, whose coverage can still be incomplete. No SDK state equals merge authority.

**Tech Stack:** Python stdlib contracts/tests and owned job logic; optional reviewed HTTP/storage/identity components outside kernel. First pilot uses one service process and tenant-scoped SQLite metadata plus private report storage; production topology must earn its own evidence.

**Spec:** [E10 child specification](../specs/2026-10-03-e10-service-api.md).

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

1. Identity strings and URLs supplied by callers never authorize access (Task 1).
2. Same idempotency key with another tenant/revision/policy cannot share a job (Task 2).
3. Cancellation/crash/report-storage failure cannot return complete analysis (Task 2).
4. Webhook replay/forgery and app revocation cannot start or publish work (Task 3).
5. Private/hosted workers and report stores must enforce tenant/source-retention boundaries separately (Task 4).

## File and interface map

- Task 1: create `service/contracts.py`, `service/openapi.json`, `service/api.py`, `sdk/pullraptor_client.py`; versioned authorized interfaces and thin client.
- Task 2: create `service/jobs.py`, `service/storage.py`; idempotency, cancellation and tenant storage.
- Task 3: create `service/github_app.py`, `service/webhooks.py`; connector lifecycle and authenticated event transport.
- Task 4: create `deploy/hosted/profile.json`, `deploy/private/profile.json`, `docs/service-operations.md`, `tests/test_service_deployment.py`; actual source-transfer, isolation and recovery acceptance.

### Task 1: Specify and validate the service request/report API

**Acceptance:** E10-A1.

**Files:** create `service/contracts.py`, `service/openapi.json`, `service/api.py`, `sdk/pullraptor_client.py`; test: `tests/test_service_api.py`.

**Interfaces:**
- Consumes: kernel Report/ReviewContract and E11-approved authorization interface when enabled; local development uses a deny-by-default test authority.
- Produces: `submit(request: ServiceRequest, principal: Principal) -> AuthorizedJob`, `get_job(job_id: str, principal: Principal) -> AuthorizedJob`, `get_report(job_id: str, principal: Principal) -> Report`, `cancel(job_id: str, principal: Principal) -> AuthorizedJob`, `capabilities(principal: Principal) -> CapabilityDocument`; Principal(tenant_id, subject_id, grants_revision), CapabilityDocument(schema, admitted_rows); SDK uses the same schema, not kernel imports.

- [ ] **Step 1: Write the failing acceptance tests.** Add `test_arbitrary_url_path_denied`, `test_wrong_tenant_each_endpoint`, `test_unknown_fields_and_version`, `test_limit_failure_preserved`, and `test_sdk_coverage_roundtrip`. For an unauthorized report request, deny before report bytes are read; supported report schema 1 full and limit_failure are both preserved.

Expected assertions for the stated adverse fixture:

```python
assert authorization.status == "denied"
assert report_bytes_read == 0
assert roundtrip["analysis_complete"] is False
```

- [ ] **Step 2: Run the focused suite and confirm a meaningful failure.** Run `PYTHONPATH=src:. python3.12 -m unittest tests.test_service_api -v`. Missing new interfaces may fail import initially; existing code must fail the new adverse assertion before correction.
- [ ] **Step 3: Implement the declared interfaces.** Version endpoints under `/v1`, publish JSON schema/OpenAPI and compatibility fixtures, strictly decode bounded data and map authorized repo IDs through a connector registry. Pin base policy independently. The SDK only submits/retrieves typed data and preserves gaps; no implicit execution/publication permissions.
- [ ] **Step 4: Run the same suite.** Require all named assertions to pass, including the successful fixture; retain raw outputs and exact input/tool identities.
- [ ] **Step 5: Commit the reviewed task on an allowed feature branch.** Stage only this task's files; use commit message `feat: define authorized review service API`. Do not commit to `main`.

### Task 2: Persist recoverable bounded job state

**Acceptance:** E10-A2.

**Files:** create `service/jobs.py`, `service/storage.py`; test: `tests/test_service_jobs.py`.

**Interfaces:**
- Consumes: Task 1 ServiceRequest/AuthorizedJob and explicit StoragePolicy(root, tenant_namespaces, retention, quotas).
- Produces: `enqueue(request: ServiceRequest, principal: Principal, idempotency_key: str) -> AuthorizedJob`; `transition(job_id: str, expected_state: str, next_state: str, receipt: JobReceipt) -> AuthorizedJob`; JobReceipt(request_digest, worker_digest, report_digest, coverage_state, cause).

- [ ] **Step 1: Write the failing acceptance tests.** Add `test_idempotency_all_semantic_inputs`, `test_tenant_key_collision_denied`, `test_cancel_worker_race`, `test_crash_recovery_partial`, `test_report_write_failure_not_completed`, and `test_queue_storage_quota`. A failed report write cannot transition a job to completed; replay of a cancelled request cannot silently resubmit.

Expected assertions for the stated adverse fixture:

```python
assert job.state == "failed"
assert job_receipt.cause == "report_storage_failed"
assert analysis_complete is False
```

- [ ] **Step 2: Run the focused suite and confirm a meaningful failure.** Run `PYTHONPATH=src:. python3.12 -m unittest tests.test_service_jobs -v`. Missing new interfaces may fail import initially; existing code must fail the new adverse assertion before correction.
- [ ] **Step 3: Implement the declared interfaces.** Use immutable input/request identities, transactional compare-and-set state and atomic bounded report storage. Do not persist secrets in metadata; isolate tenant namespaces and avoid foreign caches. Reconcile running jobs after crash, enforce queue/storage/deadline caps and terminate cancelled worker trees.
- [ ] **Step 4: Run the same suite.** Require all named assertions to pass, including the successful fixture; retain raw outputs and exact input/tool identities.
- [ ] **Step 5: Commit the reviewed task on an allowed feature branch.** Stage only this task's files; use commit message `feat: persist bounded recoverable review jobs`. Do not commit to `main`.

### Task 3: Authorize app events and completion delivery

**Acceptance:** E10-A3.

**Files:** create `service/github_app.py`, `service/webhooks.py`; test: `tests/test_service_webhooks.py`.

**Interfaces:**
- Consumes: Tasks 1–2 contracts and E02 publication gate; accepted E11-A1/A2 before remote activation.
- Produces: `accept_platform_event(raw_body: bytes, headers: dict[str, str], policy: HookPolicy) -> EventDecision`; HookPolicy(origin, credential_reference, repository_allowlist, max_age_seconds), EventDecision(accepted, event_id, cause); `deliver_completion(event: CompletionEvent, destination: ApprovedDestination) -> DeliveryReceipt` with ApprovedDestination(origin, path, key_reference) and DeliveryReceipt(event_id, attempts, state).

- [ ] **Step 1: Write the failing acceptance tests.** Add `test_invalid_signature_before_parse`, `test_duplicate_delivery`, `test_uninstalled_app_denies_queued_publish`, `test_completion_replay_tenant_denied`, `test_unapproved_destination_no_credentials`, and `test_redirect_dns_rebinding_denied`. Duplicate valid events are reconciled using delivery IDs and semantic context, not dispatched twice.

Expected assertions for the stated adverse fixture:

```python
assert duplicate_event.accepted is False
assert credential_sent_to_unapproved_origin is False
```

- [ ] **Step 2: Run the focused suite and confirm a meaningful failure.** Run `PYTHONPATH=src:. python3.12 -m unittest tests.test_service_webhooks -v`. Missing new interfaces may fail import initially; existing code must fail the new adverse assertion before correction.
- [ ] **Step 3: Implement the declared interfaces.** Validate platform signatures over bounded raw bodies before parsing; reacquire authorized repo/PR/base-policy context. Use installation-scoped credentials only in connectors and recheck revocation before work/publication. Own completion signing with event/time/body/tenant binding, receiver replay window 300 seconds, delivery-ID deduplication and at most 3 retries/30 seconds to approved HTTPS destinations. Platform delivery freshness follows its documented fields rather than inventing an unavailable timestamp.
- [ ] **Step 4: Run the same suite.** Require all named assertions to pass, including the successful fixture; retain raw outputs and exact input/tool identities.
- [ ] **Step 5: Commit the reviewed task on an allowed feature branch.** Stage only this task's files; use commit message `feat: authenticate review app and completion events`. Do not commit to `main`.

### Task 4: Exercise hosted and private profiles separately

**Acceptance:** E10-A4.

**Files:** create `deploy/hosted/profile.json`, `deploy/private/profile.json`, `docs/service-operations.md`, `tests/test_service_deployment.py`; test: `tests/test_service_deployment.py`.

**Interfaces:**
- Consumes: Tasks 1–3 and accepted E11-A1/A2; E07 runtime artifacts.
- Produces: hosted/private deployment receipts, capability/cost/retention matrices and E10 acceptance record.

- [ ] **Step 1: Write the failing acceptance tests.** Add `test_source_transfer_requires_org_policy`, `test_private_no_egress`, `test_cross_tenant_worker_store_denied`, `test_terminal_scratch_deleted`, `test_restart_mid_job`, and `test_remote_sdk_cli_api_canonical_equal`. With remote transfer disabled, reject before source acquisition/upload; private deterministic operation must survive denied egress. E10-A4 owns CLI/API/SDK profile parity; E08-A4 subsequently owns MCP/client parity and cannot be a prerequisite for accepting this service profile.

Expected assertions for the stated adverse fixture:

```python
assert transferred_source_bytes == 0
assert terminal_source_scratch_exists is False
assert remote_canonical == installed_cli_canonical
```

- [ ] **Step 2: Run the focused suite and confirm a meaningful failure.** Run `PYTHONPATH=src:. python3.12 -m unittest tests.test_service_deployment -v`. Missing new interfaces may fail import initially; existing code must fail the new adverse assertion before correction.
- [ ] **Step 3: Implement the declared interfaces.** Provision only reviewed explicit profiles; select region/storage/key boundaries and operator cost cap before any remote pilot. Mount tenant-scoped immutable inputs, deny worker egress/credentials, authorize report access and enforce deletion. Exercise submit/retrieve/cancel/repeat/revoke/crash/recovery on both profiles with independent enforcement evidence. Keep enterprise-readiness claims gated on E11-A3.
- [ ] **Step 4: Run the same suite.** Require all named assertions to pass, including the successful fixture; retain raw outputs and exact input/tool identities.
- [ ] **Step 5: Commit the reviewed task on an allowed feature branch.** Stage only this task's files; use commit message `feat: validate scoped service deployment profiles`. Do not commit to `main`.

## Package acceptance and handoff

- [ ] Re-run this package's focused suites and the affected existing suites in the trusted development environment; reviewed-source execution uses only an accepted runner.
- [ ] Exercise the scoped install/connect → exact review → visible coverage → repeat after changes → revoke/uninstall flow where this package exposes a delivery surface.
- [ ] Record all E10-A1 through E10-A4 criteria, dependency/license inventory and actual resource measurements in `docs/acceptance/E10.md`.
- [ ] Obtain independent acceptance review. Until then retain the actual implementation state and acceptance pending in the master plan. Accepted subsets do not mark the broader package complete.
