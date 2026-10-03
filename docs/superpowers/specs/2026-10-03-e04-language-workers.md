# E04: Declared language workers and capability admission specification

Date: 2026-10-03. Status: proposed child design; acceptance pending.

**Parent:** [Master plan](../../../Master-Plan.md), [product specification](2026-10-03-pullraptor-design.md), [mathematical core](../../mathematical-core.md), [security architecture](../../security-architecture.md), [evaluation](../../evaluation.md), and [execution contract](../../planning-contract.md).

## Outcome and scope

Keep generic diff available for all admitted text. First semantic wave: JS/TS and Go; second: Java/C#; third: Rust/PHP/Ruby/C/C++. Each language can release a syntax/structure subset independently; calls, CFG, dataflow and authorization require separate evidence. Swift, Kotlin, Scala, shell and SQL remain generic-diff-only targets unless separately planned.

## Dependencies and delivery boundary

E01/E02 trust acceptance and the usefulness pilot gate breadth expansion. E07 distributes optional components. E05 consumes only accepted dataflow/CFG facts; adding a grammar does not satisfy E05.

## Architecture and records

Own the coordinator and rule algorithms. Add frozen LanguageRequest(contract_digest, scope_keys, language, grammar_digest, capability, source_blobs) and LanguageResult(contract_digest, completed_keys, content_facts, unsupported, producer_digest). An operator-owned registry maps language/capability to pinned trusted executable and explicit environment. Validate worker results independently against requested scope; workers never pick their own completeness.

## Resource, dependency and compatibility budget

Each worker message is at most 8,388,608 bytes, depth 64 and 100,000 aggregate items; at most 2 seconds/blob under the 60-second review budget. Proposed per-worker RSS cap 256 MiB, 2 concurrent language workers and 1,000 authored coordinator lines. Optional installs must fit the 100-MiB extras target or receive a measured scope decision. Record every parser/runtime/license/digest before admission; no auto-download or reviewed project build/import.

## Acceptance criteria

Each criterion is required for the named scope. Cases are future checks; none was run in this planning change.

| ID | Required behavior and evidence |
|---|---|
| E04-A1 | Protocol adversarial inputs, missing/wrong/duplicate receipts and startup/credential sentinels preserve coordinator authority; completed cached and clean runs match full canonical reports. |
| E04-A2 | JS/TS and Go independently meet span/version/abstention and ≥30-positive/≥30-negative-or-unknown per-capability held-out gates plus real-repository evaluation. Generic diff remains truthful for absent workers. |
| E04-A3 | Every planned language has separate version/capability state, dependency inventory and held-out receipts; no unearned semantic tier. Grouping/diagrams preserve relation kinds, unknowns and safe rendering; graph reachability never suppresses an unsupported security obligation. |

## Failure and claim policy

Missing optional binaries/packages are unavailable capabilities, with generic diff still available under an explicit narrower profile. Required semantics return exit 2 on unsupported input. Bound overflow cannot imply a negative fact. Initial language observations are advisory; default defect blocking requires evaluation's per-stratum n ≥100, Wilson lower bound ≥0.90 and clustered held-out evidence.

**Implementation plan:** [E04 tasks](../plans/2026-10-03-e04-language-workers.md). Save acceptance in `docs/acceptance/E04.md`; use the execution contract's evidence fields and independent acceptance decision.
