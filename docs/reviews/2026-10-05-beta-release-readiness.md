# Beta release planning review

Date: 2026-10-05. Human scope: update Master Plan and all necessary release plans/tasks, with a fan of subagent reviews; no implementation or builds.

Source/trusted-main inspection: `8c2622e060b59f93c3482afec96bc472c5de3ac2`. Local HEAD: `6f1b9d370f6332e88675d3bf2b681713b6840e44`. Existing unrelated uncommitted work was preserved. Planning review is not independent product acceptance.

Reviewed artifacts: [Master Plan](../../Master-Plan.md), [release readiness plan](../superpowers/plans/2026-10-05-beta-release-readiness.md), [release queue](../release-tasks.json), [build board](../build-task-board.md), and [worker handoff](../worker-dispatch.md).

Three read-only subagents independently reviewed kernel/evaluation coverage, distribution/provenance/installation, and scope/authority/dependencies using the portable [reviewer persona](../personas/reviewer.md). They inspected project files statically and did not execute product code, tests or builds. The coordinator integrates their findings; these reviews do not accept E01, E07 or a beta.

## Findings and corrections

| Finding | Owner | Planning correction | Product evidence |
|---|---|---|---|
| Installed E01 checks preceded the artifact producer | Kernel/installation coordinator | BR-03/05 now collect source-CLI evidence; BR-10 repeats offline/user-flow checks against BR-09 artifact bytes | not_run |
| Required real-repository benchmark lacked assignment | Benchmark owner | BR-06 now records licensed pinned real-repository measurements separately from synthetic/adverse results | not_run |
| BR-11 verification lacked BR-10 artifact dependency | Documentation owner | BR-11 completion depends on BR-10; preparation_requires preserves early drafting | not_run |
| Optional capability admission existed only in prose | Scope/evidence coordinator | BR-01 produces capability-gates mapping; 20 conditional admission rows inventoried by BR-08 and admitted at BR-14, including publisher/MCP/secret/pilot and remote essentials | not_run |
| Release recovery rehearsal followed publication | Release/support owner | Disposable recovery rehearsal and runbook moved to BR-11, consumed by BR-14 before readiness; BR-17 consumes them for any authorized live recovery | not_run |
| Release mutation ownership was ambiguous | Release/dependency owner | BR-08/09 source/version/containment paths explicitly owned; dispatch rule includes referenced child-card outputs | not_run |
| Optional artifact acceptance blocked its own construction | Scope/release coordinator | Conditional rows separate BR-08 construction inventory from BR-14 final admission; candidate build/install can progress with owned pending evidence while actual activation remains gated | not_run |

All three reviewers performed focused rechecks after corrections and reported no remaining issue in their assigned review scope. Kernel review confirmed source-before-artifact sequencing and real-repository measurement ownership; distribution review confirmed mutation ownership and prepublication recovery; scope review confirmed conditional admission and removal of the artifact-acceptance cycle. These are planning reviews only.

## Static verification

Run `python3 docs/reviews/artifacts/beta-release-readiness/validate_plan.py` from the project root. The saved [validation output](artifacts/beta-release-readiness/validation.json) reports release-task fields, existing-card/criterion references, acyclic prerequisites, optional admission ownership, Markdown/JSON parity, local links and adverse negative controls. It imports only Python standard-library modules and does not import or execute PullRaptor.

Run `git diff --check` for whitespace. Source/template/task status claims were checked against tracked paths and the actual acceptance records. Historical registry revisions remain intact and explicitly marked historical in the board/handoff. New task paths remain proposed outputs. No package/task acceptance was promoted at planning time; all 18 release tasks were pending/not_run in this review.

**Construction follow-up (same date, separate authorization):** Human-requested beta implementation on `feat/beta-0.1-release-readiness` advanced BR-01–BR-14 to partial construction evidence (`docs/releases/beta-0.1-release-manifest.json`). This planning review is unchanged; independent BR-07/BR-13 and maintainer gates still block readiness.

## Decision and limitations

Coordinator planning self-review is complete after static checks and focused subagent rechecks. Product correctness, performance, independent acceptance, artifact builds, installs, actual isolation, pilots and external publication remain unrun by this documentation change. BR-01 must confirm beta scope/version/profiles/owners; no release date is invented. Full E01–E11 scope remains owned; a first wheel-only beta can earn only a declared distribution subset, with remaining E07 obligations visible.
