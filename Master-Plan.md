# PullRaptor Master Plan

Date: 2026-10-03. Status: proposed design and implementation plan; awaiting user review. No product code has been implemented.

## Intended outcome

Build a practical PR reviewer with most of the valuable modern review workflow, expressed through a small mathematical kernel rather than a large hosted platform. Accuracy and understandable evidence take priority over nominal feature count. Keep code, dependencies, installation, and operations small. Keep competing product names out of all project files.

The user delegated selection of the best combination after research. The recommended combination is local CLI plus GitHub CI, optional AI, and developer/team use. The first semantic target is Python because its parser is available in the chosen runtime. The language choice is an assumption for review, not a user-confirmed preference.

## Decision record

| Decision | Proposed choice | Reason / consequence |
|---|---|---|
| Core runtime | Python 3.12.x only initially; additional minor versions need compatibility tests | Short implementation, built-in AST, TOML, hashing, subprocess, JSON |
| Runtime dependencies | Zero third-party packages in the deterministic kernel; Git executable required | No mandatory model SDK, graph database, vector service, web framework, or container |
| Distribution | Source CLI first; packaged CLI after a build-only dependency review | Python must already be installed; this is not a single executable |
| Authority | Exact-revision evidence and a separate policy evaluator | Context and generated suggestions cannot authorize merge |
| Language strategy | Generic diff everywhere; declared semantic tiers per adapter | No claim of universal deep analysis |
| Storage | Optional atomic JSON cache outside reviewed trees | No required daemon/database; cache is disposable |
| AI | Disabled by default; provider-neutral bounded adapter later | Broader reasoning costs resources and may transfer source |
| Publication | Explicit CLI/CI action through a separate platform adapter | Local review has no external side effects |
| Learning | Maintainer-reviewed declarative preferences | Feedback cannot silently weaken security policy |
| Originality | Independent implementation of a measurable change-analysis contract | No claim of unprecedented research or competitive accuracy |

## Releases and independent work packages

Each package needs its own implementation review. Only E01 currently has a detailed execution plan.

| Package | Target | Deliverable | Exit gate | Status |
|---|---|---|---|---|
| E01 | 0.1 | Offline revision review kernel, Python patterns, generic diff summaries, evidence receipts, JSON/Markdown/SARIF, cache | Determinism, clean/incremental equivalence, safe snapshot handling, explicit coverage | Proposed |
| E02 | 0.2 | Two child packages: immutable staged/unstaged snapshots; GitHub CI/publication, lifecycle, draft/path controls | Snapshot race handling; fork isolation, stale-head rejection, retry/idempotency tests, publish preview | Proposed |
| E03 | 0.3 | Optional AI review/chat, pinned issue and CI-failure context, explanations, test/doc suggestions | Grounded claims, prompt-injection cases, bounded cost, no AI-only blockers | Proposed |
| E04 | 0.4 | Optional language workers; start JS/TS and Go, then Java/C#, then Rust/PHP/Ruby/C/C++ | Per-language capability matrix and held-out quality gate; syntax support is not dataflow support | Proposed |
| E05 | 0.5 | Bounded source-to-sink analysis, authorization obligations, local secret patterns, lockfile advisories, scanner import | Explicit assumptions, taint and sanitizer negatives, redaction, no unsound unreachable suppression | Proposed |
| E06 | 1.0 | Patch validation, isolated regression runner, agent/editor adapter, reviewed preferences, polished install | Patch preconditions, actual execution receipts, clean re-analysis, feature acceptance audit | Proposed |

Target numbers express order and intended scope, not completion dates. E04 can add grammars in parallel, but each claimed analysis capability must earn its own release evidence. E05 initially covers narrow modeled Python flows; other languages remain explicit gaps until evaluated.

## Breadth without a large core

The capability catalog has 30 items. The proposed 1.0 scope includes 26, with four deferred: reviewer/queue management, post-merge automation, runtime telemetry, and cloud/enterprise posture. That is an internal unweighted planning checklist, not measured parity with any product. Conditional language and security capabilities cannot be checked off merely because a command exists.

Six indispensable user flows govern 1.0: local review, repeat review after a push, clear summary, actionable exact-line findings, explain/challenge a finding, and propose a patch with truthful validation status. These must all work end to end. More checkboxes cannot compensate for a broken core flow.

## Gates

1. Review and accept the design and initial implementation plan before product implementation.
2. Complete E01 with zero hidden network calls and no reviewed-code execution.
3. Demonstrate E02 on same-repository and fork PRs without exposing publisher credentials to analysis.
4. Admit AI, parsers, scanners, or execution workers only with a child spec, dependency manifest, measurable benefit, and failure policy.
5. Use independently labeled held-out data before enabling default blocking for a defect detector.
6. Publish only the features and language tiers for which evidence exists.

## Resource and complexity targets

E01 target: at most 3,000 nonblank, noncomment production Python lines in at most 15 modules. This excludes tests and future adapters; it is a review trigger, not a reason to remove validation or compress unreadably.

Combined 1.0 targets: at most 8,000 production lines including authored adapters; core installed artifact at most 5 MiB; all reviewer extras at most 100 MiB; at most four third-party Python runtime packages in any single active profile and twelve across all extras. Every external binary/runtime and transitive dependency must be inventoried. Interpreter, Git, model weights and isolated runner images are measured separately, never hidden in a “zero dependency” total. Do not bundle models or scanner databases into the default install. The deterministic kernel alone retains the zero-package requirement. These are proposed budgets; exceeding them needs a measured scope/cost decision.

On a documented 2-vCPU, 4-GiB Linux runner, the initial benchmark target is p95 cold review at most 30 seconds, warm review at most 5 seconds, and peak RSS at most 512 MiB for a pinned 10,000-file / 128-MiB fixture with at most 200 Python source files, 20 changed Python files and 2,000 changed lines. The remaining files are data/documentation inventory; this is not a latency claim for 10,000 semantic source files. Real repository and adverse-input measurements are required separately. These targets have not been measured. Default safety limits are in the specification.

## Deferred scope

No mandatory hosted dashboard, billing system, organization graph service, embedding index, continuous background agents, cloud inventory, telemetry backend, cross-service runtime proof, or automatic merge. Supporting other Git platforms is a later adapter decision; their APIs are not part of E01.

## Next concrete action

Review [the specification](docs/superpowers/specs/2026-10-03-pullraptor-design.md) and [the E01 plan](docs/superpowers/plans/2026-10-03-review-kernel.md). If implementation is subsequently authorized, build E01 and measure its limits before committing to the wider release scope.
