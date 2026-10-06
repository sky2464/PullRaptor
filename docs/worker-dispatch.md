# Coordinator dispatch and unblock record

## 2026-10-06 post-publication (beta 0.1.0b1 on main)

| Field | Value |
|---|---|
| Tag / source OID | `4dcd8ab466a26241c9651e73696495a32127fa09` |
| Package version | `0.1.0b1` |
| Manifest | `ready_for_release`, `publication_authorized`, `released_verified` **true** |
| Independent reviewers | E01 and E07 beta subset accepted (see scope JSON) |
| Customer verification | BR-17 download, digest, venv install, smoke |
| Published wheel SHA-256 | `d44d6da0e6fc667a26260896cd5f4d82c35b59f8126e65ce38d92d9a8e97be24` |
| Manifest file | [beta-0.1-release-manifest.json](releases/beta-0.1-release-manifest.json) |

**Next coordinator actions:** (1) docs/install and Master Plan aligned with manifest (hygiene PR); (2) prune merged release branches; (3) assign `E02-T2-BIND` evidence fixtures and `E02-T2-INTEGRATE` on `feat/e02-publisher-integrate`; (4) parallel E01 Task 9 / BR-02 rebaseline; (5) defer `0.1.0b2` until [beta-0.1.0b2-entry-criteria.md](releases/beta-0.1.0b2-entry-criteria.md) triggers. Do not enable customer `pullraptor-publish` until E02 acceptance and capability gates authorize it.

## 2026-10-06 independent acceptance assignment (beta 0.1.x)

| Field | Value |
|---|---|
| Candidate source OID | `f834f19e9b48c90fea35338c6940004b6a5fc459` |
| Wheel SHA-256 | `b1d8df90023868ba666408318d96a1075720082faf6a86c51e6af42ecc05f700` |
| Code HEAD (docs-only delta) | `d56aae623e1daaedb2127f2607761c5198e29f12` |
| Trusted base | `8c2622e060b59f93c3482afec96bc472c5de3ac2` |
| E01 reviewer | `sme_reviewer_agent_e01_2026_10_06` (persona: `docs/personas/reviewer.md`) |
| E07 reviewer | `sme_reviewer_agent_e07_2026_10_06` (separate session; same persona) |
| Implementer exclusion | PRs #55–#58 construction; excluded from independent acceptance |
| E01 mode/paths | `verify`; `docs/acceptance/artifacts/E01/independent-review.md`, `docs/acceptance/E01.md` |
| E07 mode/paths | `verify`; `docs/acceptance/artifacts/E07/independent-review.md`, `docs/acceptance/E07.md` |
| Publication | GitHub Release `v0.1.0b1`; BR-15 requires human_coordinator authorization |

Historical note (2026-10-05): construction on `feat/beta-0.1-release-readiness` preceded merge to `main` and publication. The [release manifest](releases/beta-0.1-release-manifest.json) now records publication complete; the paragraphs below are retained for audit trail only.

Construction branch work includes CI beta install smoke (`scripts/ci_beta_install_smoke.sh`), git-archive release builds (`release/build.py`), and E01 synthetic benchmark tooling. Candidate wheels for `0.1.0b1` were rebuilt at merge/tag OID `4dcd8ab…` before publication.

## Historical construction record (2026-10-03)

Date: 2026-10-03. Assigned code/trusted base: `28b623ab1bb238ef11fbf07b29c1c773522a4a42`. Source/static reviews inspected `fbf9f2e659cda27d64b431fe4e690b2accf2a17d`; only the README title differs at the assigned base. Earlier inventories retain their original revisions. Scope: coordinator-owned planning, bounded build task definitions and worker unblock repairs. Product execution, deployment and acceptance are not inferred from this record.

## Resolved blocker and current authority

The worker report “E04–E11 blocked until child specs/plans exist” describes an earlier document-availability gap, not a human instruction to freeze the roadmap. PRs [6](https://github.com/sky2464/PullRaptor/pull/6), [7](https://github.com/sky2464/PullRaptor/pull/7), [8](https://github.com/sky2464/PullRaptor/pull/8), [9](https://github.com/sky2464/PullRaptor/pull/9), [10](https://github.com/sky2464/PullRaptor/pull/10), [11](https://github.com/sky2464/PullRaptor/pull/11), [12](https://github.com/sky2464/PullRaptor/pull/12) and [13](https://github.com/sky2464/PullRaptor/pull/13) merged those documents into the inspected base. Every E01–E11 owner now has a specification/plan in the [master index](../Master-Plan.md). The missing-document blocker is resolved at that revision. A worker on an older checkout must inspect the assigned revision before repeating it.

The human has assigned the lead responsibility for clearing worker blockers, improving plans/tasks and maintaining quality. The current request requires every planned package to have concrete build assignments. This remediation provides their task cards, interface decisions, construction dependencies and acceptance/activation gates; it also preserves earlier evidence corrections. A subsequent concrete implementation or verification assignment must record its authorized scope; a permanent historical “planning-only” label cannot veto it. Neither a worker nor this queue can grant publication, reviewed-target execution, remote source transfer, merge authority or product acceptance.

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

## Complete build queue

The [build board](build-task-board.md) and [machine-readable cards](build-tasks.json) replace the earlier preparation-only Q01–Q03 queue. All 35 E02–E11 plan tasks and E01 Task 9 have owners, bounded scope, exact input/proposed output paths, interfaces, test names/commands, adverse cases and next actions. [Coordinator decisions](build-interfaces.md) repair missing bounded stdin, ordered Python statement IR, report-to-publication binding and stale MCP capture-consumer contracts. Historical helper work remains partial until integration and required evidence exist.

Use the assigned code/trusted base above. At actual dispatch, supply the immutable document OID containing this registry, decisions and applicable child plan. Verify every input at that revision, including code inputs if a later PR changes them. An unrun acceptance command is future work; a future output file is not a missing input. “Ready” means local construction can begin under a pinned assignment; task-output predecessors and actual component admission are enforced where consumed. This queue does not silently execute tests or activate live capabilities.

Publisher contract integration (`feat/e02-publisher-contract-integration`, merged via PR #41) bound reports through `publisher.py` with inert connector tests. CLI/MCP `capture_local` consumer parity (`E02-T1-CONSUMERS`) merged via PR #43; capture hardening merged via PR #45; publication binding validator merged via PR #46 (`E02-T2-BIND` implementation partial — fixtures/evidence open). Next construction branch: `feat/e02-publisher-integrate` (`E02-T2-INTEGRATE`); then `E02-T3-LIFECYCLE` / `E02-T3-WRITES` / `E02-T4-TEMPLATE` or independent E03/E04 frontier cards per the build board. Keep at most main plus one or two current PR branches.

Construction order is a graph of reviewed task outputs. It does not use whole E10/E11/E08 package acceptance as a cycle. Local service contracts/jobs precede enterprise grants/policy essentials; accepted E10-A1/A2 and E11-A1/A2 then gate actual remote pilots. E10-A4 owns CLI/API/SDK profile evidence; E08-A4 consumes it for remote MCP parity; E11-A3 accepts operational readiness. E06 pure plans/refusal behavior can be built before actual synthetic control evaluation; actual target launch still requires independently accepted E06-A2.

E01 full assertion/corpus/cache/output/benchmark and independent review; E02 actual CI separation and usefulness pilot; parser/runtime/license admission; E07 artifact/install evidence; actual issuer/key/client/profile/region/retention/cost choices; and enforced isolation remain owned tasks or explicit external gates. They do not cancel unrelated construction. Preserve the [E01 cache/output assertion map](acceptance/artifacts/E01/2026-10-03-cache-output-assertion-map.md) and earlier suite output; reconcile against exact required assertions rather than names/counts.

## Coordinator assignment template

```text
Card(s): <exact registry IDs; identify independent part if applicable>
Mode: prepare | implement | verify | activate | release
Code OID: 28b623ab1bb238ef11fbf07b29c1c773522a4a42 (refresh explicitly after intervening code changes)
Trusted base OID: 28b623ab1bb238ef11fbf07b29c1c773522a4a42
Document OID: <immutable revision containing cards/decisions/current child>
Originating authorization and allowed operations: <bounded human/coordinator scope>
Allowed paths and language/rule/client/profile: <copy card scope; proposed outputs may be absent>
Reviewed prerequisite outputs: <exact task IDs + evidence revision, or none>
Development verification environment: <explicit trusted runtime/fixture controls, or not assigned>
Separate activation/admission gates: <copy card; record denied/not_run where unmet>
Owner: <assigned worker>; coordinator: <lead>; independent reviewer: <different reviewer>
Evidence outputs: <commands, immutable fixtures, expected outcomes, raw outputs and acceptance IDs>
```

The coordinator resolves a blocker by supplying the input, assigning its prerequisite card, repairing the task contract or recording the exact operator/external decision. Reissue the dependent card when that consumed requirement is met. Workers cannot silently shrink scope, select trusted policy or self-accept quality. Product statuses change only from real work and independently accepted evidence.

## Unblock checks

1. Inspect/fetch the assigned revision; resolve every master-index spec/plan link at that revision. Record which input was missing if one fails.
2. Match every child acceptance ID to its exact plan task. Separate required inputs from future files to create.
3. Validate task-level dependency order, particularly E10/E11/E08 and E06 boundary evaluation. Preserve pilot, runtime/license and actual isolation gates.
4. Compare the worker assignment's mode with allowed operations. Preparation never silently runs tests; development verification never authorizes reviewed-target execution.
5. Save passed/failed/not_run/stale evidence separately from document presence. Reassign the next independent task even when a later activation gate remains blocked.

These checks establish a usable planning handoff. Product and release acceptance remain pending.
