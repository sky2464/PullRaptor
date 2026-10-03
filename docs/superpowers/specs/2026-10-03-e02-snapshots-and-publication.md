# E02: Immutable local snapshots and trusted PR publication specification

Date: 2026-10-03. Status: proposed child design; acceptance pending.

**Parent:** [Master plan](../../../Master-Plan.md), [product specification](2026-10-03-pullraptor-design.md), [mathematical core](../../mathematical-core.md), [security architecture](../../security-architecture.md), [evaluation](../../evaluation.md), and [execution contract](../../planning-contract.md).

## Outcome and scope

E02A captures staged or tracked working-tree content without executing filters or changing the developer's index, refs or worktree. Untracked files require an explicit opt-in. E02B analyzes same-repository/fork PRs in a disposable boundary and previews/publishes COMMENT feedback through a separate credentialed connector. The existing snapshot/publisher modules are partial inputs; a unit-test CI workflow is not the hardened review template.

## Dependencies and delivery boundary

E01 acceptance is required for review claims. E07's accepted pinned artifact is required for hostile CI. E02A can be completed locally before E02B; the wider-delivery usefulness pilot follows both. E10's app lifecycle is separate; no hosted service is needed.

## Architecture and records

Keep filesystem capture, coordinator review, platform authorization and publication separate. Add frozen LocalSnapshot(tree_oid, base_tip, manifest_digest, capture_mode, include_untracked, discovery_complete, diagnostics) and PublicationContext(repository_id, pr_number, workflow_id, run_id, artifact_digest, reviewer_digest, head, base_tip, comparison_base, policy_digest, scope_digest). The connector independently derives this context; report fields cannot grant publication authority. Stable obligation keys and revision observations remain separate.

## Resource, dependency and compatibility budget

Inherit kernel byte/deadline bounds. Capture uses the same invocation start and at most 10 seconds within the overall review budget. Publication accepts at most 8,388,608 report bytes, posts one summary and at most 10 inline comments, with at most 3 reconciled attempts and 30 seconds total. CI analysis uses 2 vCPU/4 GiB, no egress, no secrets, no persistent shared cache; record actual OS enforcement. Budget for new authored adapter code: 1,200 nonblank lines. Pin action/artifact digests and inventory CI/container costs under E07; no new kernel package.

## Acceptance criteria

Each criterion is required for the named scope. Cases are future checks; none was run in this planning change.

| ID | Required behavior and evidence |
|---|---|
| E02-A1 | Stable tracked/index content matches bytes/modes; untracked files default off; race, symlink, linked-worktree and hostile filter fixtures preserve index/refs/worktree and never execute repository content. |
| E02-A2 | Reject stale/missing/abbreviated identities, base-policy/scope drift, cross-PR replay, tampered origin and invalid inline locations; exact current context alone can pass the separate publication gate. |
| E02-A3 | Duplicate/reordered events and lost POST responses cause no blind duplicate writes; only owned comments are updated, changed witnesses remain visible, dismissal does not refute evidence, and caps preserve the report. |
| E02-A4 | Pinned/minimally privileged template and actual fork/same-repository runs prove credential, filesystem, egress and artifact separation; unavailable isolation refuses hostile mode. Run the evaluation contract's ≥30-PR/≥3-repository/two-maintainer pilot with predeclared thresholds before widening delivery. |

## Failure and claim policy

Snapshot races, unknown object acquisition or omitted required paths make analysis incomplete. Invalid artifact/context binding rejects publication. Failure to post preserves the full report and a separate publication-failed receipt. No inline publication from limit_failure; a bounded incomplete summary remains explicit. Dismissal never means repaired. Revalidate context immediately before each write and mark later drift outdated.

**Implementation plan:** [E02 tasks](../plans/2026-10-03-e02-snapshots-and-publication.md). Save acceptance in `docs/acceptance/E02.md`; use the execution contract's evidence fields and independent acceptance decision.
