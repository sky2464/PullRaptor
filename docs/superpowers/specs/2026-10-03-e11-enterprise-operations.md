# E11: Enterprise identity, policy and operational acceptance specification

Date: 2026-10-03. Status: proposed child design; acceptance pending.

**Parent:** [Master plan](../../../Master-Plan.md), [product specification](2026-10-03-pullraptor-design.md), [mathematical core](../../mathematical-core.md), [security architecture](../../security-architecture.md), [evaluation](../../evaluation.md), and [execution contract](../../planning-contract.md).

## Outcome and scope

SSO/provisioning lifecycle, organization/repository/report/cache permissions, central declarative policy, source-free audit, secrets/key rotation, deletion/backup recovery, quotas/service health and controlled upgrade/rollback. Include a minimal administration interface through authenticated API/CLI. Billing, analytics, automatic merge and cloud-infrastructure posture analysis stay deferred.

## Dependencies and delivery boundary

E10-A1/A2 local API/job contracts precede identity/store integration. E11-A1/A2 essentials are accepted before E10-A3/A4 remote source pilots. E11-A3 completes after deployment pilot evidence; full E11 acceptance gates enterprise-ready claims. E07 artifacts and E02 trusted-policy/publication gates remain prerequisites for release/runtime claims.

## Architecture and records

Own the authorization evaluator and audit/policy contracts; provider protocol/crypto/storage primitives can be optional reviewed components outside the kernel. Principal and grants revisions bind tenant/repo access. OrganizationPolicy(revision, issuer, repository_scope, required_capabilities, destinations, retention, quotas) is declarative and base-bound. AuditEvent(event_id, actor, tenant_id, action, resource_id, decision, policy_revision, timestamp) contains no source/secrets. Revocation is rechecked at every operation and before publication, never inferred from a report or model.

## Resource, dependency and compatibility budget

Proposed essentials fit E10's 4-vCPU/8-GiB pilot host and 16-job global cap; authorization target p95 ≤100 ms and revocation effective ≤60 seconds, with immediate fresh checks before privileged writes. Audit ≤4,096 bytes/event and 90-day retention, report maximum 7 days, metadata 30 days, source scratch removed on terminal job; shorter tenant policies prevail. Online deletion completes within 24 hours; backup source/report retention ≤30 days with deletion tombstones preventing resurrection. Recovery targets: RPO ≤24 hours, RTO ≤4 hours; rollback target ≤15 minutes on the declared pilot topology. These are unmeasured targets. Proposed enterprise adapter/admin code ≤1,500 lines and minimal admin client ≤1 MiB; no vendor SDK or enterprise control enters the kernel.

## Acceptance criteria

Each criterion is required for the named scope. Cases are future checks; none was run in this planning change.

| ID | Required behavior and evidence |
|---|---|
| E11-A1 | Wrong issuer/audience/replay/expiry/cross-tenant/name-collision cases deny; scoped roles, provisioning/revocation and credential/key rotation work end to end, with ≤60-second revocation and immediate privileged-operation rechecks. |
| E11-A2 | Policy provenance cannot be weakened by head/proposals, tenant secrets/keys and audits remain isolated/source-free, and measured live deletion ≤24 hours/backup expiry ≤30 days plus tombstone-aware restoration prevent resurrection. |
| E11-A3 | Hosted/private pilots exercise real incident, revocation, backup deletion-aware restore, migration/rollback and fair quotas; measured recovery targets and cost/health evidence pass with no unresolved critical trust failure before enterprise-ready claims. |

## Failure and claim policy

Unverifiable identity, stale grants or unavailable authorization deny access. Policy conflicts and missing required capabilities remain explicit and do not relax enforcement. Audit/storage/rotation/deletion failures block affected privileged operations or release admission and produce bounded source-free diagnostics. Hosted and private readiness are separate accepted profiles; a working endpoint is insufficient.

**Implementation plan:** [E11 tasks](../plans/2026-10-03-e11-enterprise-operations.md). Save acceptance in `docs/acceptance/E11.md`; use the execution contract's evidence fields and independent acceptance decision.
