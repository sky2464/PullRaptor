# E01–E11 build task readiness review

Date: 2026-10-03. Planning review only. Code/trusted base: `28b623ab1bb238ef11fbf07b29c1c773522a4a42`. Three source reviews initially inspected `fbf9f2e659cda27d64b431fe4e690b2accf2a17d`; `git diff` confirms only a README title change between those revisions. This review grants no product acceptance.

## Scope and result

The [task board](../build-task-board.md), [registry](../build-tasks.json) and [interface decisions](../build-interfaces.md) cover 35 current E02–E11 child tasks and E01 Task 9 through 71 bounded cards. E01's historical Tasks 1–8 are audited through Task 9. Every card has an owner role, observed implementation state, scoped files/interfaces, future checks, adverse cases, next action, independent review owner and separate activation gates. All 38 acceptance IDs and all 32 capability IDs are reconciled; deferred capability portions remain deferred. E04–E11 are not blanket blocked by missing child documents.

The local construction graph is acyclic, with 18 cards at the ready frontier. Reviewed-output dependencies and producer-bound future inputs differ from actual integration/activation prerequisites. Cards using handcrafted schema fixtures cannot claim actual parser, artifact, client, isolation or service acceptance. Actual external decisions have their own owner/tasks; no live issuer, credential, source destination, deployment or spend is guessed.

## Static validation

Command, from this checkout:

```text
python3 docs/reviews/artifacts/build-task-readiness/validate_queue.py .
git diff --check
```

The standard-library checker performs no project imports or product execution. It verifies unique IDs/required fields; every pinned existing input; future-output producer ownership; task/acceptance/capability coverage; dependency references/order; declared readiness; local links and source test declarations. It rejects eight adverse registry variants: missing owner, duplicate ID, unknown dependency, unearned readiness, self-cycle, two-node cycle, missing child task and missing acceptance ID. Validation passed; `git diff --check` passed. Checker runtime was Python 3.14.7 for static documentation validation only; this does not admit that minor version to the product runtime matrix.

Saved [raw results](artifacts/build-task-readiness/validation.json) include content digests of the three handoff files. The inspection found 159 test declarations; no test success is inferred. Existing E01 suite outputs remain at their original revisions. Product/build/benchmark/pilot commands listed in the cards are future work and were not run by this planning review.

## Independent review and repairs

- Core handoff reviewer inspected E01/E02/E03/E07. Resolved missing bounded stdin dependency for capture, producer-bound future inputs and E03 per-request versus aggregate token limits. Final disposition: no actionable planning issues in that scope.
- Dependency/mathematical reviewer inspected E04/E05/E06. Resolved current DEVNULL worker input, missing ordered statement IR, shared lowering/CFG/authorization deadline, fresh/no-cache binding, input shadowing, operation union/subset consistency, exact P0 preconditions/P1 application and synthetic-schema versus actual integration prerequisites. Final disposition: no remaining issues in the correction scope.
- Delivery/authority reviewer inspected E08/E09/E10/E11. Resolved exact CommonJS entry point, connector descriptor prerequisite, subject/grants-aware idempotency, read/privileged-operation grants checks, service criteria/profile gates, E11 job-contract dependency and fake evaluator readiness. Final disposition: no remaining findings in the reviewed construction/activation-gate scope.

The master, dispatch and all current child plans link the cards/decisions. E02/E07 status text records observed helpers/scaffolding as partial; no acceptance checkbox or package state was promoted. The stale MCP capture import is assigned for repair, not claimed fixed by this documentation change. No kernel/runtime dependency or CI policy was changed.

## PR verification assignment and remaining gates

The coordinator assigns the existing trusted-base CI workflow to verify this documentation PR in its declared Python 3.12 development environment and container job. Scope is PullRaptor's development checks and static self-review; no reviewed customer repository execution is authorized. The workflow is unchanged. CI outputs are PR evidence separate from this static record and cannot accept E01–E11.

Required implementation/acceptance work remains explicitly tasked: full E01 assertion/cache/corpus/10k-file benchmark/independent review, E02 end-to-end publisher/actual CI/usefulness pilots, E03 bounded completion, E07 actual build/provenance/clean installs, per-language/model admission, E06 enforced runner boundary, local client matrices, and actual remote identity/policy/profile/operations evidence. Recommended next branch is `feat/e02-publisher-contract-integration`. The registry defines the concrete route to unblock every consuming task.
