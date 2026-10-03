# E10: Versioned review service, SDK, app and deployments specification

Date: 2026-10-03. Status: proposed child design; acceptance pending.

**Parent:** [Master plan](../../../Master-Plan.md), [product specification](2026-10-03-pullraptor-design.md), [mathematical core](../../mathematical-core.md), [security architecture](../../security-architecture.md), [evaluation](../../evaluation.md), and [execution contract](../../planning-contract.md).

## Outcome and scope

A versioned review API for submit/status/report/cancel/capabilities, a thin SDK, authenticated completion webhooks, scoped GitHub App lifecycle and separate hosted/private profiles. No arbitrary server filesystem paths/repository URLs, shared parser cache, model calls by default, billing or broad analytics dashboard. Patch-only requests explicitly declare reduced context.

## Dependencies and delivery boundary

E01/E02/E07 acceptance is required for analysis/publication/runtime claims. Develop E10-A1/A2 API/job contracts locally first; accept E11-A1/A2 identity/isolation/retention essentials before any remote source pilot in E10-A3/A4. Complete E11-A3 operations before claiming enterprise readiness. This subgate order avoids requiring the entire enterprise rollout before local API development.

## Architecture and records

Keep service/API/SDK/connector code outside the kernel in service/ and sdk/. Add ServiceRequest(tenant_id, repository_id, base_tip, comparison_base, head_or_snapshot, policy_origin, scope, profile, reviewer_digest), AuthorizedJob(job_id, tenant_id, repository_id, request_digest, state), and CompletionEvent(event_id, tenant_id, job_id, report_digest, state, issued_at). Trusted service resolution independently authorizes identities and creates coordinator scope. Job states are queued/running/completed/cancelled/failed/expired; completed means a report was stored, whose coverage can still be incomplete. No SDK state equals merge authority.

## Resource, dependency and compatibility budget

Proposed first-pilot host: 4 vCPU/8 GiB, 2 concurrent analysis workers, 10 queued jobs/tenant, 16 active jobs globally, ≤1-MiB submit envelope and ≤8-MiB report. Source snapshot limits inherit 128 MiB/10,000 entries. Job wall deadline 120 seconds including ≤60-second kernel review. API control operation target p95 ≤1 second excluding analysis. Initial retention: source scratch removed on terminal job, reports 7 days, metadata 30 days unless organization policy is shorter; source-free audit 90 days. Proposed service code ≤2,000 nonblank lines, compressed service image ≤512 MiB, SDK ≤1 MiB. Pin and inventory HTTP/TLS/storage/identity components; maximum four third-party Python runtime packages/profile. Hosted cost cap is an operator-set nonzero deployment requirement measured in pilot, not a guessed currency claim.

## Acceptance criteria

Each criterion is required for the named scope. Cases are future checks; none was run in this planning change.

| ID | Required behavior and evidence |
|---|---|
| E10-A1 | Every endpoint and SDK preserves versioned full/limit-failure, coverage and exact identities; wrong-tenant/repo/URL/path/unknown-schema requests deny without source/report disclosure. Local contract acceptance precedes remote enablement. |
| E10-A2 | Crash/cancel/storage/quota/adversarial replay cases retain recoverable truthful states and tenant separation; completed report storage never erases coverage failure. Idempotency includes all semantic and authorization dimensions. |
| E10-A3 | Signature/replay/destination/revocation and ambiguous-delivery cases preserve exact authorization and idempotency; source/provider/publisher credentials never enter workers. Actual app install/review/revoke flow is recorded. |
| E10-A4 | Actual hosted/private flows independently establish tenant/job isolation, explicit source/model destination policy, quotas/retention/failure recovery and canonical parity with CLI. Region, operational cost and limitations are measured; enterprise readiness awaits E11 operations. |

## Failure and claim policy

Authorization is checked at submit/status/report/cancel/capabilities and delivery time; unavailable identity enforcement denies access. Request reuse includes tenant/repository/revisions/policy/scope/reviewer identity. A terminal failure/cancel does not become completed. A stored incomplete report remains incomplete even with successful HTTP status. Connector/API availability and analysis completeness are different receipts. Unknown data transfer/retention or isolation stops remote admission.

**Implementation plan:** [E10 tasks](../plans/2026-10-03-e10-service-api.md). Save acceptance in `docs/acceptance/E10.md`; use the execution contract's evidence fields and independent acceptance decision.
