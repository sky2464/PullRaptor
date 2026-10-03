# E11: Enterprise identity, policy and operational acceptance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish organization authorization and operational evidence for controlled hosted/private releases.

**Architecture:** Own the authorization evaluator and audit/policy contracts; provider protocol/crypto/storage primitives can be optional reviewed components outside the kernel. Principal and grants revisions bind tenant/repo access. OrganizationPolicy(revision, issuer, repository_scope, required_capabilities, destinations, retention, quotas) is declarative and base-bound. AuditEvent(event_id, actor, tenant_id, action, resource_id, decision, policy_revision, timestamp) contains no source/secrets. Revocation is rechecked at every operation and before publication, never inferred from a report or model.

**Tech Stack:** Python stdlib policy/contracts/tests; optional standards-based SSO/provisioning, TLS/key-management and storage interfaces outside the kernel, pinned and license-reviewed before deployment.

**Spec:** [E11 child specification](../specs/2026-10-03-e11-enterprise-operations.md).

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

1. Same email/name or tenant IDs in input cannot grant organization membership (Task 1).
2. Revoked or reprovisioned users/tokens lose report/cache and publication access (Task 1).
3. Head/user/model policy proposals cannot alter the trusted organization baseline (Task 2).
4. Deleting live data must not resurrect it through backup restore or expose secret audit payloads (Task 2).
5. Upgrade/rollback and incident recovery must preserve policy/artifact identities and truthful job states (Task 3).

## File and interface map

- Task 1: create `service/identity.py`, `service/authorization.py`, `service/admin.py`; tenant/grant authority and minimal management interface.
- Task 2: create `service/org_policy.py`, `service/audit.py`, `service/retention.py`, `service/secrets.py`; central policy provenance and data lifecycle.
- Task 3: create `deploy/enterprise/release-policy.json`, `docs/enterprise-runbook.md`, `tests/test_enterprise_operations.py`; upgrade, backup/recovery and service health acceptance.

### Task 1: Enforce SSO, lifecycle and repository-scoped authorization

**Acceptance:** E11-A1.

**Files:** create `service/identity.py`, `service/authorization.py`, `service/admin.py`; test: `tests/test_enterprise_identity.py`.

**Interfaces:**
- Consumes: E10 Principal/API contracts and operator-pinned IdentityPolicy(issuer, audience, organization_bindings, verification_keys, provisioning_origin).
- Produces: `authenticate(assertion: bytes, policy: IdentityPolicy) -> Principal`; `authorize(principal: Principal, action: str, resource: ResourceIdentity, grants: GrantSnapshot) -> AccessDecision`; ResourceIdentity(tenant_id, repository_id, kind, id), GrantSnapshot(revision, memberships, roles, revoked_ids), AccessDecision(allowed, cause, grants_revision).

- [ ] **Step 1: Write the failing acceptance tests.** Add `test_wrong_issuer_audience_expiry`, `test_same_email_cross_tenant_denied`, `test_each_report_cache_repo_permission`, `test_deprovision_and_key_rotation`, and `test_stale_grants_before_publish_denied`. Roles are viewer(report/capabilities), reviewer(submit/cancel own authorized jobs), publisher(separate publish) and admin(policy/identity/retention); source submission does not grant publish.

Expected assertions for the stated adverse fixture:

```python
assert decision.allowed is False
assert decision.cause == "revoked_principal"
assert queued_publication_executed is False
```

- [ ] **Step 2: Run the focused suite and confirm a meaningful failure.** Run `PYTHONPATH=src:. python3.12 -m unittest tests.test_enterprise_identity -v`. Missing new interfaces may fail import initially; existing code must fail the new adverse assertion before correction.
- [ ] **Step 3: Implement the declared interfaces.** Use verified standards-based OIDC SSO and explicit lifecycle-provisioning connector behind pinned issuer/audience/key policy; review any external verification/crypto library and transitive licenses before import. Bind groups to grants through administrator policy, not untrusted email matches. Check current grants on all API/admin/report/cache operations and privileged writes. Test actual configured identity-provider lifecycle before E11-A1 acceptance.
- [ ] **Step 4: Run the same suite.** Require all named assertions to pass, including the successful fixture; retain raw outputs and exact input/tool identities.
- [ ] **Step 5: Commit the reviewed task on an allowed feature branch.** Stage only this task's files; use commit message `feat: enforce enterprise identity and scoped grants`. Do not commit to `main`.

### Task 2: Bind policy, audit, secrets and deletion to tenants

**Acceptance:** E11-A2.

**Files:** create `service/org_policy.py`, `service/audit.py`, `service/retention.py`, `service/secrets.py`; test: `tests/test_enterprise_controls.py`.

**Interfaces:**
- Consumes: Task 1 authorization, E10 tenant storage and OrganizationPolicy/AuditEvent records.
- Produces: `resolve_policy(organization: OrganizationPolicy, base_policy: bytes, principal: Principal) -> EffectivePolicy`; EffectivePolicy(digest, origins, required_capabilities, destinations, retention, quotas); `delete_tenant_data(tenant_id: str, policy: OrganizationPolicy) -> DeletionReceipt`; DeletionReceipt(tenant_id, live_deleted_at, backup_expiry, tombstone_digest, state).

- [ ] **Step 1: Write the failing acceptance tests.** Add `test_head_policy_cannot_weaken_org`, `test_unapproved_model_destination_denied`, `test_audit_redacts_source_and_secrets`, `test_rotation_does_not_inherit_worker_credentials`, `test_live_delete_then_restore_no_resurrection`, and `test_cross_tenant_key_store_denied`. Restore after a deletion tombstone must not expose the old report/source; policy conflicts remain denied.

Expected assertions for the stated adverse fixture:

```python
assert restored_deleted_report_accessible is False
assert secret_value not in audit_bytes
assert effective.required_capabilities >= organization.required_capabilities
```

- [ ] **Step 2: Run the focused suite and confirm a meaningful failure.** Run `PYTHONPATH=src:. python3.12 -m unittest tests.test_enterprise_controls -v`. Missing new interfaces may fail import initially; existing code must fail the new adverse assertion before correction.
- [ ] **Step 3: Implement the declared interfaces.** Resolve declarative organization/base policy without scripts, preserve all origins and conflict diagnostics, separate connector/publisher/provider keys and require encryption/key-owner receipts for each hosted/private profile. Audit decision/actor/revision without source. Enforce live/scratch/report/metadata/audit/backup retention independently, apply durable tombstones during restore and provide explicit deletion failure state. Accept E11-A2 before remote pilots.
- [ ] **Step 4: Run the same suite.** Require all named assertions to pass, including the successful fixture; retain raw outputs and exact input/tool identities.
- [ ] **Step 5: Commit the reviewed task on an allowed feature branch.** Stage only this task's files; use commit message `feat: enforce enterprise policy and data lifecycle`. Do not commit to `main`.

### Task 3: Accept controlled releases and operational pilot

**Acceptance:** E11-A3.

**Files:** create `deploy/enterprise/release-policy.json`, `docs/enterprise-runbook.md`, `tests/test_enterprise_operations.py`; test: `tests/test_enterprise_operations.py`.

**Interfaces:**
- Consumes: Tasks 1–2, accepted E10 deployed profiles and E07 release provenance.
- Produces: OperationalReceipt(profile, artifact_revision, policy_revision, topology, incident_case, observed_rpo, observed_rto, rollback_seconds, unresolved) and E11 acceptance record.

- [ ] **Step 1: Write the failing acceptance tests.** Add `test_upgrade_inflight_jobs_truthful`, `test_database_backup_restore`, `test_bad_artifact_or_policy_rollback`, `test_quota_no_tenant_starvation`, `test_incident_revocation`, and `test_health_not_analysis_completeness`. Run at least a seven-day operational pilot with daily failure/recovery exercises and hosted/private profiles separated; planned objectives remain unaccepted if no failure occurs to measure.

Expected assertions for the stated adverse fixture:

```python
assert failed_upgrade_active_version == previous_accepted_version
assert cancelled_job.state != "completed"
assert service_healthy_does_not_override_partial_report is True
```

- [ ] **Step 2: Run the focused suite and confirm a meaningful failure.** Run `PYTHONPATH=src:. python3.12 -m unittest tests.test_enterprise_operations -v`. Missing new interfaces may fail import initially; existing code must fail the new adverse assertion before correction.
- [ ] **Step 3: Implement the declared interfaces.** Document admin roles, secret rotation, data deletion, outage triage and disaster recovery; exercise signed/pinned artifact admission, migration compatibility and rollback with immutable policy identities. Measure RPO≤24h, RTO≤4h, rollback≤15min and authorization/service/job quotas against actual declared topology. Record outages and open gaps, then obtain independent operational acceptance.
- [ ] **Step 4: Run the same suite.** Require all named assertions to pass, including the successful fixture; retain raw outputs and exact input/tool identities.
- [ ] **Step 5: Commit the reviewed task on an allowed feature branch.** Stage only this task's files; use commit message `test: verify enterprise release and recovery operations`. Do not commit to `main`.

## Package acceptance and handoff

- [ ] Re-run this package's focused suites and the affected existing suites in the trusted development environment; reviewed-source execution uses only an accepted runner.
- [ ] Exercise the scoped install/connect → exact review → visible coverage → repeat after changes → revoke/uninstall flow where this package exposes a delivery surface.
- [ ] Record all E11-A1 through E11-A3 criteria, dependency/license inventory and actual resource measurements in `docs/acceptance/E11.md`.
- [ ] Obtain independent acceptance review. Until then retain the actual implementation state and acceptance pending in the master plan. Accepted subsets do not mark the broader package complete.
