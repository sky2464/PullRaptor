# Roadmap planning coverage audit

Date: 2026-10-03. Inspected implementation base: `2d0ef52` on `main`. Documentation branch: `docs/complete-master-plan`. Scope: read-only source/test/workflow inspection and planning amendments; no runtime, benchmark, installation or platform pilot was executed.

## Findings and current states

| Package | Observed artifacts at the inspected revision | Why full acceptance remains pending |
|---|---|---|
| E01 | `src/pullraptor/kernel.py`, `models.py`, `evidence.py`, parser/cache/render/CLI modules and corresponding tests; historical kernel-plan tasks checked | No `docs/acceptance/E01.md` or linked raw benchmark/corpus/user-flow acceptance record; checked tasks and present tests cannot establish all exit gates. Task 9 now defines the audit. |
| E02 | `git_snapshot.freeze_working_tree`, CLI staged/workdir flags, `publisher.py`, working-tree/publisher tests and development CI | Workdir capture uses `git add --all` with automatic untracked capture and no explicit race receipt; full base-policy/scope/artifact binding, stable inline lifecycle, ambiguous-write reconciliation and actual hostile review-template isolation are not established. E02-A1–A4 define required completion. |
| E03 | `ai_adapter.py`, optional CLI/model explanations, typed proposals, sanitization/render tests and a historical narrow spec/plan | Exact pinned issue/CI/context sessions, mandatory-witness budget behavior and actual-address/egress provider transport acceptance have no full acceptance record. E03-A1–A3 supersede broader completion claims. |
| E04–E06 | No language-worker, security-model, patch-validation/runner/preference implementation modules observed | Proposed child specs/plans now define interfaces, finite scope, adverse cases, budgets and acceptance IDs; implementation is unexecuted. |
| E07 | `pyproject.toml`, CLI/publisher/MCP entry points, Dockerfile and container/build CI | No clean-machine/offline release/provenance/update/rollback evidence. Docker uses a mutable base tag, defaults to tests and configures global `safe.directory '*'`; Python metadata admits unverified minors. E07-A1–A3 cover release completion. |
| E08 | `mcp_server.py`, MCP tests, standalone skill and `integrations/vscode/package.json` | Manifest points to `out/extension.js`, but no extension source/output/package, client plugin bundles, remote MCP or compatibility/install evidence was observed. E08-A1–A4 cover full delivery. |
| E09–E11 | No Azure connector, review service/API/SDK/app or enterprise control/operations implementation observed | Proposed child documents now cover all requested delivery tracks; execution, deployment and acceptance remain pending. |

These are planning/evidence gaps, not a comprehensive vulnerability assessment or proof of absent functionality outside the inspected checkout. Existing runtime tests were read but not run. Earlier Complete labels were normalized to actual implementation/acceptance states, preserving historical checkboxes and narrow child documents.

## Planning amendments

- E02/E04/E05/E06/E07/E09/E10/E11 received scoped child specifications and implementation plans; E03/E08 received full-scope completion specifications/plans linked from their historical subset documents.
- Every child defines exact task/file/interface ownership, test names and expected adverse outcomes, acceptance IDs, dependency/resource budgets and failure policy. All new task boxes remain unchecked.
- The master plan now indexes E01–E11, maps F01–F32 to owners or explicit deferral, distinguishes proposed/partial/implemented from acceptance, and names the next acceptance sequence.
- `docs/planning-contract.md` specifies the worker gate and independent revision-bound acceptance record. Missing plans/criteria/prerequisites/isolation must be reported before execution; a worker cannot accept its own smaller scope.
- E10 local API/job contracts precede E11 identity/policy essentials; remote pilots follow those essentials, and E11 operational acceptance follows pilots. This removes a package-level service/enterprise dependency cycle.

## Platform mechanisms checked for the proposed designs

Official documents checked on 2026-10-03 define mechanisms, not product acceptance:

- [MCP 2025-06-18 transports](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports) supports the separate proposed remote Streamable HTTP contract and requires Origin validation; legacy stdio compatibility is a separate claim.
- [GitHub webhook validation](https://docs.github.com/en/webhooks/using-webhooks/validating-webhook-deliveries) supports raw-body signature validation before event processing; deduplication/authorization/revocation remain owned application obligations.
- [Azure external PR status policy](https://learn.microsoft.com/en-us/azure/devops/repos/git/pr-status-policy?view=azure-devops) supports the proposed branch-policy/status mapping. Actual API/task/Services/Server versions must be pinned and exercised at admission.

## Documentation verification boundary

Planning completion requires all E01–E11 spec/plan links to resolve; acceptance IDs to map to tasks; all F01–F32 rows to have an owner/deferral; new task boxes to remain unchecked; no missing required child sections/placeholders; and no production/workflow/runtime artifact changes. Passing these checks establishes document consistency only. Product acceptance remains pending.

Fresh documentation checks on 2026-10-03:

| Check | Observed result |
|---|---|
| Read-only Python stdlib scan of the changed/new Markdown files | PASS: 31 files and 152 local Markdown links; every link target exists. No project modules were imported. |
| Master-plan ownership / child acceptance / capability scan | PASS: all 11 specification/plan owners; 38 acceptance criteria defined, with every new child ID mapped to its task; all 32 capability rows accounted for. |
| Proposed-task / section / placeholder scan | PASS: new task boxes unchecked; required child sections present; no unresolved planning placeholders. |
| Changed-path scope | PASS: Markdown only; no source, tests, runtime metadata, container or workflow modifications. |
| `git diff --check` | PASS, exit 0. |

The scan resolves each local Markdown target relative to its document, compares each child's acceptance-ID set against plan task IDs, expands capability ranges, and checks new plan headers/constraints/interfaces/adverse-focus/handoff sections. This is a planning consistency check, not an independent runtime or security acceptance review.
