# Evaluation and release contract

Status: proposed; no tests, benchmark datasets, or product measurements have been run. Documentation validation is separate from software validation.

## Evidence hierarchy

1. Immutable input manifests and exact source locations support reproducibility.
2. Deterministic fixtures establish specified local behaviors and adverse-case handling.
3. Metamorphic tests establish invariants across edits and cache conditions.
4. Repository-held-out independently labeled data estimates accuracy and coverage.
5. Controlled pilot review measures user usefulness, latency, noise, and cost.

One level cannot substitute for another. Green unit tests do not demonstrate user-path correctness; a benchmark score does not prove safety; accepted suggestions are not correctness labels.

## E01 required invariants

| Contract | Necessary adverse cases / expected result |
|---|---|
| Immutable comparison | Dirty tree, refs moving after resolution, shallow/missing base, multiple merge bases, replaced objects: pinned identities or explicit failure |
| Safe ingestion | Malicious filenames, spaces/tabs/newlines, symlinks, submodules, binary data, encoding failures, hostile diff config: no execution or accidental file traversal |
| Location fidelity | Unicode byte columns, CRLF, multiline AST nodes, renamed/deleted paths: side-aware valid spans or visible inability to locate |
| Scope honesty | Unsupported language/grammar, malformed Python, oversized input, parser crash, timeout: explicit partial status and exit 2 for structural profile |
| Differential reporting | Same obligation moved by edits, ambiguous alignment, baseline parse failure, changed evidence at old sink: preserve identity or mark unknown |
| Cache correctness | Completed clean/warm/corrupt/absent runs, interrupted write, runtime change, new file resolving old missing import: identical canonical output; partial runs retain their own resource receipts |
| Pattern restraint | Intentional patterns, import aliases, shadowing, nested scope, reassignment, conditional re-raise: no unsupported defect assertion |
| Offline behavior | Fail all socket/DNS entry points during a full run: core still works and creates no external side effects |
| Resource limits | Boundary and over-limit fixtures: deterministic diagnosis; no silent truncation or unbounded subprocess output |

Exhaustively enumerate evidence-pair accumulation and policy decisions over the four states. Include byte-for-byte determinism of completed canonical output. Mutation sequences must compare full coverage and diagnostic records, not merely finding counts. Separately test cold timeout versus warm completion; the program must report that difference and withhold an equivalence claim until a complete clean replay exists.

## Initial rule corpus

For each initial rule, require at least 10 focused positive and 10 counterexample/ambiguous fixtures. Some intentional patterns correctly produce an advisory pattern observation; the unacceptable result is an unsupported defect, exploit, or blocker assertion.

- PY001: repeated omitted-argument use of a directly mutated literal default, versus immutable defaults, parameter reassignment, nested-function mutation, ambiguous alias mutation, and intentional cache semantics.
- PY002: bare handlers with swallowing/return, versus unconditional re-raise, typed handlers, nested handlers, conditional re-raise and intentional interruption supervision.
- PY003: resolved shell invocation, versus shadowed names, import aliases, literal safe commands, unknown command provenance, `shell=False`, and dynamic dispatch. Without a modeled input-to-command path, never assert injection.

These fixtures do not justify default blocking. Keep pattern claims and defect claims separately labeled in the corpus.

## Held-out accuracy study

Before claiming product accuracy or enabling default defect blocking, create a pinned independently owned corpus with at least 200 revision pairs across at least 20 repositories, split by repository into development, calibration and final held-out sets. This is a proposed minimum, not statistical sufficiency for every rule. Also require enough applicable emitted findings for each calibrated stratum; dataset size alone cannot satisfy the n >= 100 gate.

Record language/runtime, rule version, real or injected defect, defect location, baseline/head relationship, expected scope, excluded files and adjudication notes. Use two independent reviewers for consequential defect labels; disputed cases remain unresolved and are reported separately. Avoid copied restricted rule corpora and record repository/fixture licensing.

Report per-language and per-rule precision, defect recall, abstention, incomplete coverage, false actionable comments per PR, duplicate rate, p50/p95 latency, peak RSS, source/context bytes and optional model requests/cost. Publish raw denominators and uncertainty; macro and pooled scores have different meanings. Keep the final test set untouched while choosing thresholds.

Default defect-blocking proposal: applicable stratum has at least 100 independently adjudicated emitted findings, nominal 95% precision lower bound at least 0.90, clustered-data evaluation, validated witness requirements, and no unresolved critical trust-boundary regression. If any condition is absent, the detector remains advisory. Severe-sounding language is not an exception to this rule.

## Language capability gates

Maintain a file-language/capability matrix. Syntax parsing, symbol resolution, call context, CFG, dataflow and authorization obligations are separate columns. Each adapter needs at least 30 held-out positive and 30 negative/unknown fixtures for each advertised semantic capability, plus real-repository evaluation. These are minima; narrow sample success does not prove comprehensive language coverage.

Include version features, unresolved imports, generated code, macros/reflection, decorators, polymorphism, framework dispatch, exception flow, and unavailable libraries. Unsupported cases must abstain or mark coverage gaps. Do not mark all capabilities supported because a grammar exists.

## Security and patch gates

Finite-domain transfers must be monotone, converge on cycles, and preserve hazard distinctions. Include wrong-context sanitizers, alternate unauthorized paths, reassigned resources, fail-open guards, unknown library effects and infeasible-path examples. A source-to-sink graph remains a modeled candidate without execution evidence.

For E06, require at least 50 validation scenarios spanning application preconditions, path traversal, symlink targets, conflict/fuzz, stale head, syntax failure, failing tests, timeout and credential isolation. Passing unrelated tests must not clear a finding. Where a reproduction exists, confirm failure before patch and success after patch with pinned commands and runner image. Mark verification “not run” when no runner is available. Passing builds/tests without a relevant baseline reproduction can be called checks passed, never regression reproduced and resolved.

## Integration gates

E02 must cover same-repository/fork PRs, missing permissions, moved head, deleted-line location, rate limiting, duplicate event delivery, ambiguous POST outcome, tampered/misassociated artifacts and report-size limits. A publisher must reconcile after a timeout rather than blindly repeat a potentially successful POST. Partial inline publication cannot erase the full local report.

E03 must cover adversarial instructions embedded in source/comments/issues/CI logs, fabricated file references, invalid output schema, missing mandatory context, provider timeout, refusal and quota limits. A real line reference must not promote an unverified behavioral claim to supported. Include exact-head CI log association, stale log rejection, redaction and oversized logs. Optional provider failures must never rewrite an incomplete review as a successful security result. Record exact prompt/model/version/context provenance where retention policy permits.

## Complexity and performance

Measure the master-plan targets on a pinned fixture and documented runner. Compare no-cache and warm runs over at least 30 repetitions, with interpreter version and RSS measurement method recorded. Include an adverse deeply nested parser input separately from typical PRs. Treat source-line/module targets as review prompts; reducing readable validation to satisfy a line count is forbidden.

Every dependency addition requires a ledger: purpose, direct/transitive packages, native binaries, license, distribution size, startup overhead, network behavior and benchmarked benefit. Build-only and development packages are separately labeled; zero-runtime-dependency claims apply only to the kernel. External Git, Python runtime and optional model hardware are real requirements. Measure the combined 1.0 footprint/code/package budgets in the master plan, including all enabled extras, so complexity cannot be hidden in adapters. Add compatibility fixtures before admitting a new Python minor runtime.

## Release record

A release candidate must save pinned input manifests, commands, exit codes, raw metrics, corpus revision, unresolved limitations and a user-flow acceptance report. Update `Master-Plan.md` only after these exist. Documentation-only planning completion must never be described as a shipped reviewer.
