# Roadmap execution and acceptance contract

Date: 2026-10-03. Status: proposed execution contract. This document completes planning coverage; it is not product acceptance or permission to implement.

## Status and execution gate

Track planning, implementation and acceptance separately. `Proposed` means no implementation was observed. `Partial implementation` means some artifacts exist but the named package is unfinished. `Implemented; acceptance pending` means production modules exist but the full exit gate has no accepted evidence record. `Accepted` requires the package's complete acceptance record. Draft specs/plans and checked task boxes cannot promote any of these states.

Before a worker starts a package, read the master plan, parent specification, mathematical core, security architecture, evaluation contract, its child specification and its child plan. Identify the exact task, input revision, requested language/capability scope and acceptance IDs. If a plan, criterion, dependency acceptance or required isolation boundary is missing, report `blocked_for_execution` with the missing item. Complete independent authorized tasks only; do not replace missing requirements with a smaller self-selected scope. Planning approval and product execution authorization are separate decisions.

All future code/test paths in child plans are proposed locations. They are not evidence that those files exist. All new task checkboxes remain unchecked. Existing checked E01 tasks and historical E03/E08 completion labels record earlier implementation claims; the current master-plan acceptance column governs roadmap completion.

## Constraints inherited by every child

- Zero third-party packages in the deterministic kernel; Git executable required.
- Python 3.12.x pinned baseline; versions 3.13+ / 3.14+ admitted only after AST parser parity verification.
- Keep competing product names out of all project files.
- CI policy comes from the trusted base tip; head configuration cannot weaken its own review.
- Never execute reviewed code in the analysis process. Only the separately accepted E06 runner may execute candidate code.
- Workers receive explicit sanitized environments, no ambient credentials and no foreign/shared caches. Local interpreter flags do not establish hostile isolation.
- Keep content facts, revision-bound observations and untrusted proposals distinct. Only the coordinator defines expected scope.
- Unknown, incomplete, conflicted and stale results remain visible. Hashes, diagrams, dismissal and passing unrelated tests do not authorize merge.
- Declarative configuration only; no repository script evaluation, automatic dependency installation or automatic merge.
- Existing kernel defaults remain 10,000 entries, 2,097,152 bytes/blob, 134,217,728 bytes/snapshot, 60 seconds/review with a 2-second finalization reserve, and 8,388,608 bytes/report. Tighter adapter limits never silently shrink required scope.
- Commits use `feat/`, `fix/`, `chore/` or `docs/` branches; all integration to `main` is through a CI-verified PR.

## Dependency and resource admission

Each child specifies a proposed measurable budget. Before execution admits a new component, create its inventory in `docs/dependencies/<package>.json`: exact version/digest, purpose, direct/transitive dependencies, binaries/runtimes, license and redistribution terms, source URL, installed/image size, startup/RSS, network destinations and measured benefit. Build/development dependencies and runtime dependencies are separate. An unreviewed or incompatible license prevents admission; it does not justify copying that component. Optional workers stay outside the deterministic kernel. No dependency is imported by this planning change.

No package may call an unmeasured target a measured result. Exceeding a budget requires an explicit scope/cost decision recorded in the acceptance record. Protocol overflow, cancellation, failed acquisition and timeout produce unavailable/partial states, not empty successful reviews. Local and hosted/private profiles earn separate evidence.

## Acceptance record

Each implementation candidate writes `docs/acceptance/E<nn>.md`, supported by artifacts under `docs/acceptance/artifacts/E<nn>/`. Include:

1. Reviewed code/artifact revision, spec/plan revisions, rule/model/grammar/runtime/client/platform versions and trusted policy origin.
2. Every child acceptance ID with command, immutable fixture/input identity, expected and observed result, exit code and raw artifact path. Include failures, exclusions and unrun checks.
3. Canonical clean/incremental/determinism comparison for completed identical logical inputs, and separate receipts for partial runs.
4. Positive, negative and adverse user-flow checks; actual boundary enforcement, dependency/license inventory and resource measurements.
5. Independently adjudicated quality/pilot evidence where required by the evaluation contract; exact denominators and unresolved disputes.
6. Independent acceptance decision and remaining limitations. The implementer cannot accept its own scope or quality labels. A prototype or subset can be recorded without accepting the whole package.

Use `passed`, `failed`, `not_run` or `stale` per criterion. A package is accepted only when every required criterion passed for its declared scope and the independent review accepted the record. Superseded code, policies, grammars or artifacts invalidate affected evidence. A report can be complete in its declared narrow scope while the broader roadmap package remains partial.

## Plan self-review and handoff

Validate local documentation links, E01–E11 plan/spec ownership, acceptance-ID/task coverage, dependency order, adverse cases, record/signature consistency, resource declarations and capability ownership. Record this separately from runtime tests. Do not run the repository's candidate code to validate a documentation-only change. Implementation begins only under a subsequent authorized execution request and the package gate above.
