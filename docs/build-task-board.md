# Build task board

Date: 2026-10-03. Code/trusted base: `28b623ab1bb238ef11fbf07b29c1c773522a4a42`.

This board turns every outstanding E01–E11 child task into a bounded worker assignment. The [registry](build-tasks.json) contains exact files, interfaces, owner roles, acceptance IDs, test names, commands, adverse cases and separate activation gates. The [interface decisions](build-interfaces.md) repair concrete gaps in the existing plans. The [dispatch contract](worker-dispatch.md) governs authority and immutable revisions. No product tests were run to create this board.

Coverage: **35 E02–E11 child tasks plus E01 Task 9**, split into **71 cards** with explicit prerequisite owners. “Ready” describes local construction, not completed acceptance. Existing helper modules and checked historical steps remain partial evidence. Deferred F26/F27/F29 and the cloud-posture part of F30 remain deferred; the registry reconciles all 32 capability IDs.

## First branch and independent work

Publisher integration through `publisher.py` is on `main` (PR #41); end-to-end E02 acceptance and pilots remain open. Next branch: `feat/e02-local-snapshot-consumers` (`E02-T1-CONSUMERS`) — shared `resolve_local_review_refs`, CLI `--include-untracked`, and MCP parity tests. Actual same-repository/fork CI (`E02-T4-TEMPLATE`) and usefulness pilots are separate evidence tasks.

Parallel frontier: E01 assertion/corpus/benchmark preparation; E03 bounded context/transport completion; E07 real artifact/provenance/install preparation; E04 receipt validators and bounded stdin; E05 statement lowering and local secret patterns; E06 refusal-first runner and patch/preference contracts; E08 session wire; E09 connector wire; E10 shared API contract. Follow the exact dependency IDs below and in the registry. Do not open every future branch at once: keep main plus one or two current PR branches; queue the rest.

## Child task coverage

| Package | Existing plan tasks covered | Current observation / acceptance |
|---|---|---|
| E01 | Task 9; historical Tasks 1–8 audited through its assertion mapping | Kernel source exists; A1/A2/A3 incomplete |
| E02 | Tasks 1–4 | Local capture and publication helpers exist; publisher/MCP integration and pilots pending |
| E03 | Tasks 1–3 | ai_adapter subset exists; context/transport/conversation completion pending |
| E04 | Tasks 1–3 | Proposed language worker/capability work |
| E05 | Tasks 1–4 | Proposed IR/security/auth/secret/import work |
| E06 | Tasks 1–4 | Proposed patch/runner/stage/preference work |
| E07 | Tasks 1–3 | Metadata and provenance helper/stub exist; actual build/install evidence pending |
| E08 | Tasks 1–4 | Stdio scaffolding/manifest/skill exist; capture consumer and session/editor/remote completion pending |
| E09 | Tasks 1–3 | Proposed Azure integration |
| E10 | Tasks 1–4 | Proposed service/API/SDK/jobs/app/profile work |
| E11 | Tasks 1–3 | Proposed identity/policy/operations work |

## Ordered worker cards

Each row is owned work, including admission/design prerequisites. A predecessor means a reviewed interface/output, not whole-package acceptance. Actual component versions, licenses, issuer/keys, remote topology and compatibility environments must be recorded by their owner before the consuming operation. Proposed output paths are files to create, not missing input blockers.

| Card | Work / owner | Local construction dependencies | Acceptance scope |
|---|---|---|---|
| `E01-T9-ACCEPT` | Independently assess the complete E01 evidence record — Independent acceptance reviewer; coordinator maintains roadmap state | E01-T9-BENCH, E01-T9-CACHE, E01-T9-CORPUS, E01-T9-MAP, E01-T9-OUTPUT, E01-T9-RECORDS | E01-A1, E01-A2, E01-A3 |
| `E01-T9-BENCH` | Build and measure the exact benchmark fixture — Benchmark/environment owner | E01-T9-MAP | E01-A3 |
| `E01-T9-CACHE` | Complete cache trust and clean/incremental equivalence — Cache/coordinator implementer; independent scope reviewer | E01-T9-MAP | E01-A1, E01-A2 |
| `E01-T9-CORPUS` | Pin initial-rule corpus and local user-flow fixtures — Fixture/corpus owner; independent label reviewer | E01-T9-MAP | E01-A1, E01-A2, E01-A3 |
| `E01-T9-MAP` | Rebaseline every required assertion and immutable fixture — Acceptance inventory worker; coordinator owns expected requirement scope | Ready: no task-output prerequisite | E01-A1, E01-A2, E01-A3 |
| `E01-T9-OUTPUT` | Complete bounded output, offline and recovery regressions — CLI/render boundary implementer; independent presentation reviewer | E01-T9-MAP | E01-A1, E01-A2 |
| `E01-T9-RECORDS` | Finish ingestion, record, worker and evidence regressions — Kernel boundary implementer; independent reviewer validates claim scope | E01-T9-MAP | E01-A1 |
| `E02-D01` | Finalize trusted publication connector and identity contract — Coordinator/security architect | Ready: no task-output prerequisite | E02-A2, E02-A3, E02-A4 |
| `E02-D02` | Finalize capture sealing and temporary storage lifetime — Coordinator/local snapshot architect | Ready: no task-output prerequisite | E02-A1 |
| `E02-T1-CAPTURE` | Finish safe bounded snapshot capture — Local snapshot implementer | E02-D02, E04-D0 | E02-A1 |
| `E02-T1-CONSUMERS` | Route local CLI and MCP through one snapshot contract — CLI/MCP integration implementer coordinated with E08 owner | E02-T1-CAPTURE | E02-A1 |
| `E02-T2-BIND` | Bind report identities, coverage and exact inline locations — Publication contract implementer | E02-D01 | E02-A2 |
| `E02-T2-INTEGRATE` | Integrate trusted binding and owned rendering into publisher — Publisher connector implementer | E02-D01, E02-T2-BIND | E02-A2 |
| `E02-T3-LIFECYCLE` | Complete stable observation identity and collision handling — Lifecycle implementer | E02-D01, E02-T2-BIND | E02-A3 |
| `E02-T3-WRITES` | Implement bounded paginated ownership and lost-response recovery — Publisher transport implementer | E02-T2-INTEGRATE, E02-T3-LIFECYCLE | E02-A3 |
| `E02-T4-PILOT-ACCEPT` | Collect scoped same-repo/fork pilot and independent E02 record — Pilot evidence owner; independent acceptance reviewer | E02-T1-CAPTURE, E02-T1-CONSUMERS, E02-T2-INTEGRATE, E02-T3-WRITES, E02-T4-TEMPLATE | E02-A1, E02-A2, E02-A3, E02-A4 |
| `E02-T4-TEMPLATE` | Replace help-only CI template with fail-closed review jobs — CI boundary implementer; independent isolation reviewer | E02-T2-INTEGRATE, E02-T3-WRITES, E07-T2-BUILD, E07-T2-VERIFY | E02-A4 |
| `E03-D01` | Record exact context, provider and conversation limits — Coordinator/provider-boundary owner | Ready: no task-output prerequisite | E03-A1, E03-A2, E03-A3 |
| `E03-T1-CONTEXT` | Build provenance-bound context selection and redacted preview — Context implementer | E03-D01 | E03-A1 |
| `E03-T2-TRANSPORT` | Build bounded approved-address AI transport — Provider-boundary implementer | E03-D01, E03-T1-CONTEXT | E03-A2 |
| `E03-T3-CONVERSATION` | Build bounded explanation and conversation envelopes — Conversation implementer; separate independent acceptance reviewer | E03-D01, E03-T1-CONTEXT, E03-T2-TRANSPORT | E03-A3, E03-A1, E03-A2 |
| `E04-D0` | Implement the bounded worker stdin interface — Coordinator/process engineer and independent boundary reviewer | Ready: no task-output prerequisite | E04-A1, E04-A2, E04-A3 |
| `E04-D1` | Pin first-wave parser/runtime inventories — Language dependency researcher and independent license/capability reviewer | E04-T1 | E04-A1, E04-A2, E04-A3 |
| `E04-D2` | Pin later-language candidates separately — Per-language parser researcher and independent evaluator | E04-T1 | E04-A1, E04-A2, E04-A3 |
| `E04-T1` | Define and validate worker contracts — Language protocol and coordinator engineer; independent scope/boundary reviewer | Ready: no task-output prerequisite | E04-A1 |
| `E04-T2` | Deliver the first JS/TS and Go structure wave — Optional parser adapter engineer; independent language evaluator | E04-T1, E04-D1 | E04-A2 |
| `E04-T3` | Admit later languages and bounded relationship presentation — Capability matrix and graph serializer engineer; per-language independent evaluators | E04-T1 | E04-A3 |
| `E05-D1` | Build owned statement IR and bounded Python lowering — Python IR/CFG engineer and independent mathematical reviewer | Ready: no task-output prerequisite | E05-A1, E05-A2, E05-A3, E05-A4 |
| `E05-D2` | Freeze trusted AuthModel and synthetic guard contract — Authorization model owner and independent reviewer | Ready: no task-output prerequisite | E05-A1, E05-A2, E05-A3, E05-A4 |
| `E05-D3` | Define offline lock/advisory/SARIF schemas and gate transport — External-data schema engineer and independent transport reviewer | Ready: no task-output prerequisite | E05-A1, E05-A2, E05-A3, E05-A4 |
| `E05-T1` | Own finite Python CFG and value-specific hazard propagation — Python statement-IR and finite-flow engineer; independent mathematical/model reviewer | E05-D1 | E05-A1 |
| `E05-T2` | Evaluate authorization as must facts — Authorization model and must-analysis engineer; independent obligation reviewer | E05-D1, E05-D2 | E05-A2 |
| `E05-T3` | Detect and redact local secret-risk patterns — Local pattern and value-free presentation engineer; independent privacy reviewer | Ready: no task-output prerequisite | E05-A3 |
| `E05-T4` | Import bounded advisories and scanner proposals — Strict external-data and lockfile importer engineer; independent transport/provenance reviewer | E05-D3 | E05-A4 |
| `E06-D1` | Freeze exact text edit and private tree backend — Patch/tree engineer and independent filesystem reviewer | Ready: no task-output prerequisite | E06-A1, E06-A2, E06-A3, E06-A4 |
| `E06-D2` | Select enforced Linux isolation and safety evaluation profile — Isolation engineer, release inventory owner and independent OS reviewer | Ready: no task-output prerequisite | E06-A1, E06-A2, E06-A3, E06-A4 |
| `E06-D3` | Define authenticated local preference approval boundary — Local policy/approval engineer and independent authority reviewer | Ready: no task-output prerequisite | E06-A1, E06-A2, E06-A3, E06-A4 |
| `E06-T1` | Validate patch paths and apply exact preconditions — Immutable patch/tree engineer; independent path/revision reviewer | E06-D1 | E06-A1 |
| `E06-T2` | Enforce a separate execution boundary — Isolation launcher engineer; independent OS/runner admission reviewer | Ready: no task-output prerequisite | E06-A2 |
| `E06-T3` | Re-analyze obligations and retain P0–P4 states — Patch evidence and stage-state engineer; independent obligation reviewer | E06-T1 | E06-A3 |
| `E06-T4` | Approve preferences through trusted declarative policy — Local preference/policy engineer; independent authority reviewer | E06-D3 | E06-A4 |
| `E07-D01` | Record exact release origin, manifest and inventory contracts — Coordinator/release owner | Ready: no task-output prerequisite | E07-A1, E07-A2, E07-A3 |
| `E07-T1-INVENTORY` | Finish distribution metadata and exact runtime/license inventory — Distribution implementer | E07-D01 | E07-A1 |
| `E07-T2-BUILD` | Implement actual reproducible candidate artifact builder — Release build implementer | E07-D01, E07-T1-INVENTORY, E07-T2-VERIFY | E07-A2 |
| `E07-T2-VERIFY` | Bind release admission to independent origin and actual bytes — Release provenance implementer | E07-D01, E07-T1-INVENTORY | E07-A2 |
| `E07-T3-INSTALL` | Validate clean installed artifacts and supported release footprint — Installation verifier; separate independent acceptance reviewer | E07-T1-INVENTORY, E07-T2-BUILD, E07-T2-VERIFY | E07-A3, E07-A1, E07-A2 |
| `E08-D1` | Pin MCP session, grant and wire schemas — MCP contract designer | Ready: no task-output prerequisite | E08-A1 |
| `E08-D2` | Pin native editor and assistant client packaging contracts — Client/package compatibility designer | E08-D1 | E08-A2, E08-A3 |
| `E08-D3` | Pin remote MCP service-authority mapping — Remote protocol contract designer | E08-D1, E10-D1, E11-D1 | E08-A4 |
| `E08-T1` | Bound stdio MCP and report/session identity — MCP/session engineer | E08-D1 | E08-A1 |
| `E08-T2` | Implement and package native editor flow — Native editor extension engineer | E08-D2 | E08-A2 |
| `E08-T3` | Package neutral assistant plugins and standalone skills — Assistant integration/package engineer | E08-D2 | E08-A3 |
| `E08-T4` | Map authenticated remote MCP to service authority — Remote MCP adapter engineer | E08-D3 | E08-A4 |
| `E09-D1` | Pin Services connector, publication and delivery adapters — Platform contract/admission designer | Ready: no task-output prerequisite | E09-A1, E09-A2, E09-A3 |
| `E09-T1` | Authorize repositories and immutable PR iterations — Platform acquisition adapter engineer | E09-D1 | E09-A1 |
| `E09-T2` | Map report lifecycle to comments and status — Platform publication/lifecycle adapter engineer | E09-D1, E09-T1 | E09-A2 |
| `E09-T3` | Package and validate task, hooks and branch policy — Platform CI/delivery engineer | E09-D1 | E09-A3 |
| `E10-D1` | Pin local API, SDK and deny-by-default authority contract — Service API contract designer | Ready: no task-output prerequisite | E10-A1, E10-A2 |
| `E10-D2` | Pin job state, idempotency, storage and cancellation contract — Job/storage contract designer | E10-D1 | E10-A2, E11-A2 |
| `E10-D3` | Pin app signatures, lifecycle and completion transport — App/webhook contract designer | E10-D1, E10-D2 | E10-A3 |
| `E10-D4` | Pin hosted/private deployment and isolation profiles — Deployment profile designer | E10-D1, E10-D2, E10-D3, E11-D1, E11-D2 | E10-A4, E11-A3, E08-A4 |
| `E10-T1` | Specify and validate local service request/report API — Service contract/API and thin SDK engineer | E10-D1 | E10-A1 |
| `E10-T2` | Persist recoverable bounded local job state — Job state/storage engineer | E10-D2 | E10-A2 |
| `E10-T3` | Authorize app events and completion delivery — App lifecycle/webhook transport engineer | E10-D3 | E10-A3 |
| `E10-T4` | Exercise hosted and private service profiles separately — Deployment/isolation acceptance engineer | E10-D4 | E10-A4 |
| `E11-D1` | Pin identity, provisioning, grants and administration adapters — Identity contract/admission designer | E10-D1, E10-D2 | E11-A1 |
| `E11-D2` | Pin organization policy, audit, key and deletion contracts — Policy/key/retention contract designer | E10-D2, E11-D1 | E11-A2 |
| `E11-D3` | Pin release, migration and operational pilot evidence — Operations experiment/release designer | E10-D4, E11-D2 | E11-A3 |
| `E11-T1` | Enforce scoped authorization and identity lifecycle — Identity/authorization engineer | E11-D1 | E11-A1 |
| `E11-T2` | Bind organization policy, audit, secrets and deletion to tenants — Organization controls/data-lifecycle engineer | E11-D2 | E11-A2 |
| `E11-T3` | Accept controlled releases and operational pilots — Operations/release acceptance owner | E11-D3 | E11-A3 |

## Dispatch and completion

The coordinator chooses a card or its documented independent part, records `prepare`/`implement`/`verify` separately, and pins the immutable document revision containing this board plus the code and trusted base. A build assignment names allowed paths, explicit development environment and reviewer; test command strings in the registry do not run themselves. Refresh the source observation when intervening PRs change a consumed interface. Rebase on trusted main through a reviewed PR, without head-defined policy weakening.

For every card, save actual diff and verification outputs, expected/observed adverse outcomes and failures/not_run states. Independent review checks interfaces before dependent integration; acceptance review separately checks every child criterion. The implementer does not approve its own completeness. Do not mark a card done from a checkbox, test name or artifact hash.

Blocker report: card/mode + code/doc/trusted-base OIDs + exact missing input/control + inspected evidence + affected operation + resolving owner + next action. Continue an independent assigned card; never turn one gate into “all E04–E11 blocked.” The coordinator repairs task definitions, schedules the dependency/admission work or records the external decision and reissues the assignment.

## Gates that remain real

- E01 needs full requirement/assertion evidence, canonical mutation/cache/corpus/replay checks, the pinned 10k-file/30-repetition p95/RSS benchmark and independent acceptance.
- E02 needs actual same-repository/fork runs proving isolation/credential/artifact separation and the predeclared ≥30-PR/≥3-repository/two-maintainer usefulness pilot before expansion. Pure publisher construction can proceed now.
- Every optional parser/build/client/transport/crypto/runner component needs exact version/digest/license/resource admission. Synthetic fixtures do not prove real compatibility or isolation.
- E06 target execution stays denied until the independently reviewed disposable synthetic-control evaluation establishes E06-A2. No host fallback.
- E10/E11 remote profiles need actual issuer/keys, scoped repository grants, approved source destinations/region/retention/cost, accepted identity/policy/isolation essentials and pilots. E08 remote parity follows the actual accepted service profile. E11 operational readiness requires its seven-day/recovery evidence.
- Publication, deployment and external release remain separately assigned operations. Local build completion does not activate them.

## Planning verification

The coordinator records static registry/link/coverage/dependency validation and independent review in `docs/reviews/2026-10-03-build-task-readiness.md`. This is planning evidence only; all candidate build/acceptance commands in the registry remain unrun by this planning change.
