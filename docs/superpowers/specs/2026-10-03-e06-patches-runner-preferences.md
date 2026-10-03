# E06: Patch receipts, isolated regression runner and reviewed preferences specification

Date: 2026-10-03. Status: proposed child design; acceptance pending.

**Parent:** [Master plan](../../../Master-Plan.md), [product specification](2026-10-03-pullraptor-design.md), [mathematical core](../../mathematical-core.md), [security architecture](../../security-architecture.md), [evaluation](../../evaluation.md), and [execution contract](../../planning-contract.md).

## Outcome and scope

Validate narrow text modifications and additions against an exact head; record P0–P4 independently. Initially reject renames/deletions, symlink/submodule/executable-bit changes and policy/workflow paths unless a separately reviewed action admits them. Candidate test/build execution belongs only to a disposable credential-free runner. Maintainer-reviewed declarative preference proposals may affect presentation or advisory rule choices, never silently weaken CI policy.

## Dependencies and delivery boundary

E01/E02 acceptance for revision/review obligations; E07 accepted image/runtime inventories for runner launch. E03 can supply an untrusted draft but is optional. E04/E05 apply only to advertised language/model re-analysis; unsupported obligations remain not_run/partial. E08 consumes receipts but cannot validate its own patch.

## Architecture and records

Add frozen PatchProposal(head, digest, allowed_paths, edits), PathEdit(path, old_blob, old_mode, new_bytes), ValidationReceipt(patch_digest, original_tree, result_tree, stages, obligation_results, execution), and StageResult(stage, status, cause). P0 preconditions, P1 exact application, P2 parse, P3 re-analysis, P4 actual isolated checks are distinct. RunnerPlan(image_digest, argv, input_tree, resource_limits, network_policy) comes only from trusted configuration. PreferenceProposal(author, source_report, scope, declarative_changes) is separate from AcceptedPreference(approver, policy_revision, proposal_digest).

## Resource, dependency and compatibility budget

Proposals ≤1,048,576 bytes, ≤10 text paths and ≤2,000 changed lines; strict shared record limits. Runner defaults: 2 vCPU, 2 GiB RSS limit, 64 processes, 120 seconds total, 8,388,608 stdout bytes and 65,536 stderr bytes, denied egress and no credentials/host sockets. Runner image target ≤512 MiB compressed, measured separately from reviewer extras. Proposed adapter code ≤1,200 nonblank lines; no runtime package in kernel. External runtime/isolation/image licenses and actual enforcement must be inventoried before launch.

## Acceptance criteria

Each criterion is required for the named scope. Cases are future checks; none was run in this planning change.

| ID | Required behavior and evidence |
|---|---|
| E06-A1 | At least 50 E06 scenarios across P0–P4 (distributed over Tasks 1–3) include stale head, mode/blob mismatch, traversal, symlink, conflict/fuzz, unsupported operations and protected paths with no working-tree mutation. |
| E06-A2 | Actual runner proves enforced filesystem/egress/credential/process/resource isolation; timeout/cancellation/output overflow cannot yield a passing check. Missing enforcement leaves P4 not_run and refuses hostile execution. |
| E06-A3 | All stage dependency combinations, stale revisions, meaningful baseline-fail/patched-pass and unrelated-pass cases preserve truthful state; full clean/incremental patched reports agree and no unproven obligation clears. |
| E06-A4 | Only explicit authorized maintainer actions admit allowlisted declarative preferences; untrusted feedback never weakens required scope/security, alters verdict authority or counts as accuracy calibration. |

## Failure and claim policy

Each stage is passed/failed/not_run/stale; failed prerequisites leave dependent stages not_run. Later head drift marks affected stages stale. No aggregate verified label substitutes for these records. checks_passed covers only configured checks; regression_reproduced_and_resolved additionally requires the relevant baseline failure and patched pass. Drafts remain reviewable after failure. Merge is outside scope.

**Implementation plan:** [E06 tasks](../plans/2026-10-03-e06-patches-runner-preferences.md). Save acceptance in `docs/acceptance/E06.md`; use the execution contract's evidence fields and independent acceptance decision.
