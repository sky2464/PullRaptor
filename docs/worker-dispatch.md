# Coordinator dispatch and unblock record

Date: 2026-10-03. Planning availability/static inventory initially inspected at `132f817e96dfd9de21051c9389a7112b6dc6f084`. Follow-on code/trusted base: `79a00f32896af7bc3270f8ea583453d0079b2962` after PR [14](https://github.com/sky2464/PullRaptor/pull/14) added suite evidence and metadata corrections. Scope: resolve planning/worker handoff blockers and reconcile acceptance evidence. Product execution, deployment and acceptance are not inferred from this record.

## Resolved blocker and current authority

The worker report “E04–E11 blocked until child specs/plans exist” describes an earlier document-availability gap, not a human instruction to freeze the roadmap. PRs [6](https://github.com/sky2464/PullRaptor/pull/6), [7](https://github.com/sky2464/PullRaptor/pull/7), [8](https://github.com/sky2464/PullRaptor/pull/8), [9](https://github.com/sky2464/PullRaptor/pull/9), [10](https://github.com/sky2464/PullRaptor/pull/10), [11](https://github.com/sky2464/PullRaptor/pull/11), [12](https://github.com/sky2464/PullRaptor/pull/12) and [13](https://github.com/sky2464/PullRaptor/pull/13) merged those documents into the inspected base. Every E01–E11 owner now has a specification/plan in the [master index](../Master-Plan.md). The missing-document blocker is resolved at that revision. A worker on an older checkout must inspect the assigned revision before repeating it.

The human has assigned the lead responsibility for clearing worker blockers, improving plans/tasks and maintaining quality. This remediation covers preparation, coordination and document repairs. A subsequent concrete implementation or verification assignment must record its authorized scope; a permanent historical “planning-only” label cannot veto it. Neither a worker nor this queue can grant publication, reviewed-target execution, remote source transfer, merge authority or product acceptance.

## Assignment and blocker contract

The coordinator gives each worker a bounded assignment containing:

| Field | Required content |
|---|---|
| Task and mode | Exact child task/step; `prepare`, `implement`, `verify`, `activate` or `release` |
| Revisions | Immutable code revision, document revision and trusted base revision; revisions may differ deliberately |
| Scope and authority | Language/rule/platform/profile, allowed paths and operations, originating human authorization |
| Inputs and outputs | Existing input locations; proposed output paths explicitly labeled as outputs |
| Evidence | Acceptance IDs, expected adverse outcomes, required commands/artifacts and honest unrun states |
| Prerequisites | Consumed task/criterion evidence, applicable runtime/dependency/isolation controls; activation/release gates separately listed |
| Owner and review | Worker, coordinator escalation owner and independent acceptance reviewer |

Before starting, verify the assigned docs exist at the document revision and match the scope. Read the [execution contract](planning-contract.md) and applicable child. Missing proposed output files are work to perform, not missing input prerequisites. Do not run target code or repository scripts to discover configuration.

A blocked worker reports task/mode, inspected revisions, missing item, evidence/location, affected operation, resolving owner and the smallest next action. It pauses that dependent operation, preserves completed evidence and continues only independent authorized work. The coordinator checks stale refs, supplies/repairs the plan, schedules prerequisite work or records a required human/external decision, then reissues the task. Unknown safety controls stay blocked. A blocker never becomes acceptance by changing a status label.

## Task-level readiness

All listed preparation work is available under this planning-remediation scope. The table does not dispatch production implementation; implementation can be assigned within later human-authorized scope without repeating the resolved missing-spec claim. Prior acceptance is required where a task actually consumes an accepted artifact or activates a capability.

| Package | Next bounded preparation task | Gates that still apply to implementation/integration/claims |
|---|---|---|
| E04 | Task 1: map protocol/schema/receipt/environment adverse cases to the owned request/result contract; prepare per-worker runtime/license inventory | E01/E02 acceptance and usefulness pilot before language expansion; actual worker controls, pinned grammar/runtime and E04-A1 before capability admission; E04-A2/A3 per-language quality evidence |
| E05 | Task 1: specify finite-domain/CFG fixture expectations; Task 3: value-free secret-pattern positive/negative inventory | E01/E02 acceptance and pilot before model expansion; E04 only for non-Python facts; E06 only for actual reproduction; E05-A1–A4 before their respective claims |
| E06 | Task 2: review RunnerPlan, deployment controls and synthetic boundary-fixture design; Task 1: patch-precondition case inventory | Accepted E07 image/runtime inventory and actual reviewed disposable evaluation controls before runner launch/fixtures; accepted E01/E02 revision/review obligations for consumed P0–P3 claims; independently accepted E06-A2 before reviewed-target execution; no host fallback |
| E07 | Task 1: audit current metadata/entry points/container defaults and prepare exact build/runtime/license inventory | Dependency admission before installation/build additions; E01 before reviewer release claims; E07-A2 provenance before artifact admission and E07-A3 per-platform installation evidence; external release separately authorized |
| E08 | Task 1: compare current stdio/session/report behavior against E08-A1; map absent extension/plugin outputs to Tasks 2–3 | E01/E02 snapshot/report and E07 installed artifact acceptance before local delivery; E03 for optional AI transport; E10-A1/A2 + E11-A1/A2 before remote activation; E10-A4 profile then E08-A4 MCP parity |
| E09 | Task 1: map repository/iteration/head/base/policy acquisition and denial cases; prepare pinned connector/version/license decisions | Accepted E07 artifact and E02 acquisition/publication contracts before actual CI/publication; scoped credentials/isolation and E09-A1–A3 evidence before platform claims |
| E10 | Tasks 1–2: finalize local versioned API/job/SDK contracts and denial/cancel/replay fixture expectations | Local contract construction does not require full E11 acceptance; consumed engine/artifact/publication claims require E01/E02/E07; E11-A1/A2 before remote pilots; E10-A4 owns CLI/API/SDK parity, not MCP acceptance |
| E11 | Task 1: define Principal/grant/revocation and tenant-denial fixtures; Task 2: policy/audit/retention mapping | E10-A1/A2 for API/job integration; actual issuer/crypto/license/control admission before identity claims; E11-A1/A2 before remote activation; E11-A3 after deployment pilots before enterprise readiness |

The service/enterprise order is E10-A1/A2 local contracts → E11-A1/A2 essentials → E10-A3/A4 deployment profiles → E08-A4 remote MCP parity and E11-A3 operations. Broader package acceptance follows all required criteria. No package waits for its own completed release to gather evidence; no endpoint activates without its required controls.

## First worker queue

This queue defines the next assignments, not an already pinned production dispatch. Use the follow-on code/trusted base above, unless the coordinator explicitly assigns the older static-inventory scope. At dispatch, the coordinator supplies the immutable document OID containing this remediation and the selected child plan; the new dispatch/static-inventory files are not present at the older inspected base. Verify those documents at that supplied OID. The initial inventory retains its original inspected plan revision; follow-on work records the corrected document revision separately. Preserve PR 14's collected suite output, but reconcile its criterion claims against exact required assertions/fixtures.

| Task | Owner / mode | Exact inputs and outputs | Current state / next action |
|---|---|---|---|
| Q01: E01 Task 9 Step 1 | Coordinator assigns acceptance worker / prepare; independent reviewer checks mapping | Code/trusted base at follow-on OID; corrective document OID supplied at dispatch; E01 Tasks 1–8, parent §§5–8, security/math/evaluation contracts → [static inventory](acceptance/E01-static-inventory.md) and `docs/acceptance/artifacts/E01/`; reconcile primary E01 record | Initial declaration inventory recorded. Continue full requirement → assertion → immutable fixture → expected result mapping; do not credit test names as behavior evidence. |
| Q02: E07 Task 1 audit | Coordinator assigns distribution worker / prepare | Same code base; corrective document OID and E07 child spec/plan supplied at dispatch → proposed `docs/dependencies/E07.json` inventory and metadata/entry-point/default comparison in `docs/acceptance/E07.md` | Ready for static audit. Record unknown version/license/measurement fields explicitly; no install/build/runtime execution in preparation. |
| Q03: E01 Task 9 Steps 2–4 | Coordinator assigns verifier and independent reviewer / verify | Completed Q01 mapping, pinned fixtures, explicitly selected trusted Python 3.12 environment and benchmark runner → raw results/per-criterion evidence | Preserve collected suite output. Additional criterion-specific runtime work needs an explicit verification assignment and suitable environment. Full mutation/output/corpus/benchmark/independent evidence remains incomplete; this is not a missing-plan blocker. |

The [cache/output assertion map](acceptance/artifacts/E01/2026-10-03-cache-output-assertion-map.md) defines bounded follow-on correction/fixture assignments: cache equality/mutations/replay; cache admission and coordinator closure; all-format fallback/deadlines/output channels; presentation/offline/recovery flows. Each identifies required outcomes and current assertion boundaries against E01 Tasks 7–8 and E01-A1/A2. Assign those separately, with the affected test paths and meaningful adverse cases; a missing fixture is not automatically a demonstrated production defect. The mapped test/helper blobs were verified unchanged at the follow-on base.

Q01 and Q02 are independent preparation tasks. The coordinator can assign subsequent local implementation tasks using their existing child plans; it must name the exact task and consumed dependencies rather than dispatch “complete E04–E11.” Read-only inventory cannot accept a package, and a worker cannot accept its own reduced scope.

## Unblock checks

1. Inspect/fetch the assigned revision; resolve every master-index spec/plan link at that revision. Record which input was missing if one fails.
2. Match every child acceptance ID to its exact plan task. Separate required inputs from future files to create.
3. Validate task-level dependency order, particularly E10/E11/E08 and E06 boundary evaluation. Preserve pilot, runtime/license and actual isolation gates.
4. Compare the worker assignment's mode with allowed operations. Preparation never silently runs tests; development verification never authorizes reviewed-target execution.
5. Save passed/failed/not_run/stale evidence separately from document presence. Reassign the next independent task even when a later activation gate remains blocked.

These checks establish a usable planning handoff. Product and release acceptance remain pending.
