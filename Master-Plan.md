# PullRaptor Master Plan

Date: 2026-10-06. Status: roadmap planning coverage complete; E01 is implemented with **beta subset** independently accepted; full E01/E07 roadmap acceptance remains pending; E02–E11 have partial implementation artifacts. Beta 0.1.x **released** as package `0.1.0b1` ([GitHub Release v0.1.0b1](https://github.com/sky2464/PullRaptor/releases/tag/v0.1.0b1); tag source `4dcd8ab466a26241c9651e73696495a32127fa09`; see `docs/releases/beta-0.1-release-manifest.json` — `ready_for_release`, `publication_authorized`, and `released_verified` are true). Trusted base for policy derivation: `8c2622e060b59f93c3482afec96bc472c5de3ac2`. Every E01–E11 package has a scoped specification/plan and acceptance criteria.

## Intended outcome

Build a practical PR reviewer whose core user flows remain understandable under incomplete analysis and hostile input, expressed through a small mathematical kernel. Accuracy, defensible evidence, and safe operation take priority over nominal feature count. Deliver broad workflow value through conditional adapters after the core demonstrates usefulness. Keep code, dependencies, installation, and operations small. Keep competing product names out of all project files.

The initial recommendation was local CLI plus GitHub CI, optional AI, and developer/team use. The expanded delivery roadmap covers packaged CLI/container, VS Code extension, repository app, CI integration, review API/SDK, hosted service, private enterprise deployment, AI-editor and terminal-assistant plugins/MCP/skills, and Azure DevOps. Customers must be able to install or connect released artifacts without manually cloning PullRaptor or embedding its source in their own application. Named client selections and references remain in the originating conversation; project records use neutral adapter roles. Generic cloud execution is covered separately by hosted deployment and cloud-session compatibility gates. These are roadmap deliverables, not implemented capabilities. The first semantic target is Python because its parser is available in the chosen runtime. The language choice is an assumption for review, not a user-confirmed preference.

## Decision record

| Decision | Proposed choice | Reason / consequence |
|---|---|---|
| Core runtime | Python 3.12.x pinned baseline; versions 3.13+ / 3.14+ admitted only after AST parser parity verification | AST node grammar, span semantics, and standard-library stability; prevents silent analyzer divergence across minor versions |
| Runtime dependencies | Zero third-party packages in the deterministic kernel; Git executable required | No mandatory model SDK, graph database, vector service, web framework, or container |
| Local environment | Standard Python 3.12 virtualenv (`.venv`); Conda excluded | Zero-dependency stdlib footprint; avoids heavy Conda binary overlays, ambient path pollution, and dynamic linking interference with `-I -S` subprocess isolation |
| CI & hostile isolation | Pinned Docker container (`python:3.12-slim`) with egress and credential restrictions | Reproducible cross-platform baseline and disposable execution boundary for untrusted PRs |
| Distribution | Versioned packaged CLI and Docker container (`python:3.12-slim`), editor/plugin packages, and service connections; source checkout is a development path | No manual PullRaptor clone for customers; declare Python/Git or bundled runtime requirements; review build dependencies and licenses |
| Integration boundary | Versioned review/report contract shared by CLI, API, MCP and platform adapters | One owned kernel; thin adapters cannot redefine scope, evidence or merge authority |
| Deployment choice | Offline local, customer CI, hosted service, and private enterprise service | Remote transfer is explicit; hosting is optional and adds separately measured operational cost |
| Enterprise access | Organization/repository-scoped identity, authorization, audit and retention controls outside the kernel | Credentials stay in narrowly scoped connectors; tenant and worker isolation require acceptance evidence |
| Authority | Exact-revision evidence and a separate policy evaluator | Context and generated suggestions cannot authorize merge |
| Language strategy | Generic diff everywhere; declared semantic tiers per adapter | No claim of universal deep analysis |
| Storage | Optional private, operator-owned parser cache; CI defaults off | Hashes/atomic writes do not authenticate facts; foreign/shared entries are misses |
| Scope authority | Coordinator-owned review contract, independently checked receipts | A worker cannot omit requested files and declare the review complete |
| Hostile analysis | Disposable credential-free isolated CI job | Local interpreter isolation does not restrict host filesystem authority |
| AI | Disabled by default; provider-neutral bounded adapter later | Broader reasoning costs resources and may transfer source |
| Publication | Explicit CLI/CI action through a separate platform adapter | Local review has no external side effects |
| Learning | Maintainer-reviewed declarative preferences | Feedback cannot silently weaken security policy |
| Originality | Independent implementation of a measurable change-analysis contract | No claim of unprecedented research or competitive accuracy |

## Releases and independent work packages

Each package has a linked scoped specification and implementation plan in the planning index below and requires its own independent acceptance record. E07–E11 expand the requested roadmap beyond the original kernel-focused 1.0 scope; they are decomposed delivery tracks, not promised dates or a claim that the original budgets cover a hosted platform. All E01–E11 contain implementation artifacts of differing completeness, but no package has complete independent acceptance. Earlier Complete labels do not establish the full exit gates.

| Package | Target | Deliverable | Exit gate | Status |
|---|---|---|---|---|
| E01 | 0.1 | Offline kernel, Python patterns, diff summaries, request/scope receipts, actionable coverage diagnostics, bounded JSON/Markdown/SARIF, private cache | Determinism, clean/incremental equivalence, trusted cache admission, bounded ingestion, independent scope validation | Implemented; acceptance pending |
| E02 | 0.2 | Two child packages: immutable staged/unstaged snapshots; hardened GitHub CI/publication, stable lifecycle, draft/path controls | Snapshot races; disposable fork isolation, current head/base/policy/scope binding, retry reconciliation, publish preview | Partial implementation; acceptance pending |
| E03 | 0.3 | Optional AI review/chat, pinned issue and CI-failure context, explanations, test/doc suggestions | Typed untrusted proposals, approved transport, prompt-injection cases, bounded cost, no AI-only blockers | Partial implementation; acceptance pending |
| E04 | 0.4 | Optional language workers; start JS/TS and Go, then Java/C#, then Rust/PHP/Ruby/C/C++ | Per-language capability matrix and held-out quality gate; syntax support is not dataflow support | Partial implementation; acceptance pending |
| E05 | 0.5 | Bounded source-to-sink analysis, authorization obligations, local secret patterns, lockfile advisories, scanner import | Explicit assumptions, taint and sanitizer negatives, redaction, no unsound unreachable suppression | Partial implementation; acceptance pending |
| E06 | 1.0 | Patch validation, isolated regression runner, reviewed preferences; shared contracts for editor/agent consumers | Patch preconditions, actual execution receipts, clean re-analysis, feature acceptance audit; install/editor deliverables owned by E07/E08 | Partial implementation; acceptance pending |
| E07 | Distribution track | Packaged CLI (`pyproject.toml`), pinned Docker container (`python:3.12-slim`), release provenance, update/rollback and offline installation | Clean-machine install without manual source clone; runtime/license inventory, provenance verification, uninstall/rollback, artifact review equivalence | Partial implementation; acceptance pending |
| E08 | Editor/agent track | VS Code extension; AI-editor and terminal-assistant plugin packages; standalone skills and local/remote MCP adapter | Per-client/version/session matrix, credential isolation, bounded protocol, stale snapshot handling, safe rendering and no unauthorized writes | Partial implementation; acceptance pending |
| E09 | Azure DevOps track | Azure Repos Git connector, Azure Pipelines template/task, service hooks, PR comments/status and organization extension packaging | Trusted-policy isolation, iteration/head/base binding, event retry reconciliation, branch-policy mapping and scoped credentials | Partial implementation; acceptance pending |
| E10 | Service track | Versioned review API, thin SDK, authenticated completion webhooks, GitHub App, hosted and private enterprise deployments | API compatibility, repository authorization, job/tenant isolation, source-transfer/retention enforcement, webhook replay tests and failure recovery | Partial implementation; acceptance pending |
| E11 | Enterprise operations track | SSO, role-based access, organization policy, audit, secrets, deployment administration and controlled releases | Cross-tenant denial, revocation, policy provenance, deletion/backup recovery, update rollback and operational pilot | Partial implementation; acceptance pending |

Target numbers express order and intended scope, not completion dates. E04 can add grammars in parallel, but each claimed analysis capability must earn its own release evidence. E05 initially covers narrow modeled Python flows; other languages remain explicit gaps until evaluated.

## Breadth without a large core

The original amended capability catalog has 32 items: 30 from the workflow study plus two from independent security/architecture review. Its kernel-focused 1.0 proposal includes 28. Enterprise delivery and governance, previously deferred within cloud/enterprise posture, are now requested through E07–E11. Reviewer/queue management, post-merge automation, runtime telemetry and cloud infrastructure posture analysis remain deferred. Delivery tracks are not extra detector capabilities and do not change the historical 28-of-32 count; reconcile the capability catalog in their child designs. That is an internal unweighted planning checklist, not measured parity with any product. Conditional language and security capabilities cannot be checked off merely because a command exists.

Six indispensable user flows govern 1.0 for demonstrated language/model tiers: local review, repeat review after a push, clear summary, actionable exact-line findings, explain/challenge a finding, and propose a patch with truthful validation status. These must all work end to end. Each flow also explains incomplete coverage and a trusted recovery action. More checkboxes cannot compensate for a broken core flow.

## External delivery and enterprise adoption

The same deterministic kernel produces a revision-bound report in every deployment. Network/authentication, job coordination, platform publication, AI providers and UI adapters remain outside it. Skills explain a workflow; MCP exposes bounded tools; plugins package those components; an editor extension supplies native presentation. None substitutes for the review engine or validates model-generated claims by itself.

| Surface | Customer experience | Delivery owner and acceptance scope |
|---|---|---|
| Packaged CLI / Docker container | Install a published release (with standard `.venv` guidance) or pull a pinned `python:3.12-slim` Docker image; review locally or in their runner | E07; support matrix, explicit runtime prerequisites and no source-checkout requirement |
| VS Code | Install extension, select base/head or immutable local changes, inspect inline findings and coverage | E08; local engine by default, explicit remote endpoint option, safe source locations and stale-result indicators |
| AI editor client | Install a PullRaptor plugin bundling skills/MCP; also allow standalone MCP/skill installation | E08; client-specific manifest/settings and optional extension compatibility tested separately |
| Terminal assistant client | Install a versioned PullRaptor plugin or standalone skill/MCP connection; request review/explanation | E08; local terminal, IDE-hosted and cloud sessions are separate compatibility claims |
| GitHub | Install an organization/repository-scoped app for hosted/private review, or use a reusable CI workflow | E02 owns CI/publication semantics; E10 owns app/service lifecycle and delivery |
| Azure DevOps | Connect selected Azure Repos Git repositories; use a service hook or Azure Pipelines task/template; receive PR comments and review status | E09; use build-validation/status branch policies for Azure Repos PRs rather than assuming YAML `pr` triggers; Services first, Server versions admitted individually |
| Custom solution | Submit/retrieve reviews through a versioned API; optionally use an SDK and completion webhook | E10; integrations consume reports without importing kernel code |
| Hosted cloud | Administrator connects repositories; developers receive reports in their existing tools | E10/E11; documented regions, source/model destinations, retention, quotas, availability and incident procedures |
| Private enterprise | Deploy released containers in customer infrastructure and connect editor/CI/API clients | E10/E11; declared egress, private identity/secrets, upgrade/backup/deletion and offline operation profile |

Customers need not clone PullRaptor. A platform installer may fetch a plugin bundle internally. The reviewer still needs authorized access to the customer's reviewed source: exact Git objects or a bounded immutable snapshot manifest. Git object acquisition stays in a connector. Patch-only submissions must declare reduced context; missing base/history/dependencies produce partial coverage. Unsaved editor changes require the E02 immutable-local-snapshot contract, not an unrecorded mutable-directory scan.

### Shared integration contract

E10 must specify a versioned API for submitting a review, obtaining job state/report, cancelling work, discovering supported capabilities and receiving completion events. A request identifies the authorized organization/repository, exact base tip/comparison base/head or local snapshot, requested scope/profile and trusted policy origin. The service resolves and authorizes these independently; supplied identity strings or arbitrary repository URLs do not grant access or network authority. Report schema follows the coordinator-owned contract. Submission idempotency includes tenant, repository, revisions, policy, scope and reviewer version; cancellation, timeout and transport failure never become a completed review.

E08 maps bounded review submission, report retrieval and capability discovery to local stdio and authenticated remote MCP transports. Explanation can use optional E03 reasoning but remains pinned to the report. MCP/SDK/skills must preserve coverage, diagnostics, language/rule/version scope and stale/conflicting/unknown evidence. They expose no arbitrary shell, filesystem traversal, URL fetching, automatic merge or unrestricted patch application. Publishing and applying a proposed patch are distinct explicitly authorized operations; baseline review access does not grant them. AI clients and skill instructions cannot weaken trusted policy or authorize their own completeness.

Keep credentials at the authenticated connector/service boundary; allowlist destinations and repository scope. Pass sanitized explicit environments to workers, with no ambient secrets or foreign/shared caches. Remote callers cannot select server filesystem paths. Bound concurrent jobs, bytes, retries and costs. Separate analysis, AI proposals, report storage and publisher identities. Revalidate platform-derived PR/iteration/head/base/policy/scope immediately before publication; duplicated/reordered hooks and ambiguous publication responses require reconciliation. Uninstall/revocation stops new work and invalidates credentials; report retention/deletion follows declared policy.

### Enterprise controls and delivery order

E11 covers SSO and lifecycle provisioning, role-based repository access, centrally managed declarative policy, audit events, credential rotation, tenant isolation, retention/deletion, encryption/key ownership, quotas and service health. Include access to reports and caches in tenant checks; report content may expose source or architecture. Private deployment and hosted isolation have separate threat models and measurable enforcement. No source or prompts are sent to a model provider by default. Remote AI requires the E03 approved transport and an explicit organization policy. User interfaces distinguish completion, incomplete analysis, publication failure and outdated results; service availability is not analysis completeness.

Dependency order: E07 packaging can begin after E01 acceptance and supply the pinned reviewer artifact for E02; E02 and its usefulness pilot gate wider delivery expansion. E08 local review depends on E02 snapshots and E07; its remote mode also depends on E10. E09 starts with the released engine and E02 publication contracts and can use customer CI before hosting. E10 builds on E07 and the trusted acquisition/publication boundaries. E11 is required before claiming enterprise-ready hosted or private service; identity/isolation/retention essentials must ship with any remote pilot. E03 is needed for AI explanation/proposals, not deterministic integration. E04–E06 are needed only for their advertised language, security or patch/execution capabilities.

Every delivery track now has a proposed child design and plan. Before implementation, pin its dependency/license inventory and compatibility matrix; enforce its declared failure policy/resource budget and meaningful adverse acceptance cases. Validate an install → authenticate/connect → review exact revisions → display coverage → repeat after changes → revoke/uninstall flow on each supported surface. Compare completed canonical reports against the packaged CLI for identical logical inputs. Pin and test transport/client/platform versions; packaging portability does not establish behavior portability. Test changed policy with unchanged head, cross-repository replay, duplicate events, expired tokens, malicious report rendering, tenant-crossing access and interrupted jobs. Acceptance remains pending for every track until its own complete evidence record and independent decision exist.

### Platform references

Checked official documentation on 2026-10-03 for integration mechanisms, not product acceptance evidence. Recheck and pin behavior when writing child specifications.

- [VS Code extension distribution](https://code.visualstudio.com/api/working-with-extensions/publishing-extension).
- [GitHub App permissions](https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/choosing-permissions-for-a-github-app).
- [Azure DevOps service hooks](https://learn.microsoft.com/en-us/azure/devops/service-hooks/overview?view=azure-devops), [Azure Repos pipeline triggers](https://learn.microsoft.com/en-us/azure/devops/pipelines/repos/azure-repos-git?view=azure-devops), and [external PR status policy](https://learn.microsoft.com/en-us/azure/devops/repos/git/pr-status-policy?view=azure-devops).

## Gates

1. Review and accept the design and initial implementation plan before product implementation.
2. Complete E01 with zero hidden network calls and no reviewed-code execution.
3. Demonstrate E02 on same-repository and fork PRs without exposing publisher credentials to analysis. Revalidate base policy and requested scope as well as head before publication.
4. Admit AI, parsers, scanners, or execution workers only with a child spec, dependency manifest, measurable benefit, and failure policy.
5. Use independently labeled held-out data before enabling default blocking for a defect detector.
6. Publish only the features and language tiers for which evidence exists.
7. Admit E07–E11 only through child designs and plans, declared dependency/resource budgets, platform compatibility checks and the integration acceptance flows above. Enterprise hosting requires isolation/access/retention evidence, not just a working endpoint.
8. Run the E01/E02 usefulness pilot before expanding language/security breadth; retain explicit partial results and measure repeated-comment noise. Apply the [security and architecture contract](docs/security-architecture.md) throughout.

## Resource and complexity targets

E01 target: at most 3,000 nonblank, noncomment production Python lines in at most 15 modules. This excludes tests and future adapters; it is a review trigger, not a reason to remove validation or compress unreadably.

Combined 1.0 targets: at most 8,000 production lines including authored adapters; core installed artifact at most 5 MiB; all reviewer extras at most 100 MiB; at most four third-party Python runtime packages in any single active profile and twelve across all extras. Every external binary/runtime and transitive dependency must be inventoried. Interpreter, Git, model weights and isolated runner images are measured separately, never hidden in a “zero dependency” total. Do not bundle models or scanner databases into the default install. The deterministic kernel alone retains the zero-package requirement. These are proposed budgets; exceeding them needs a measured scope/cost decision. E07–E11 must set separate measured budgets for containers, editor/MCP/plugin runtimes, service dependencies, storage, concurrency and operational cost before implementation; they cannot hide their costs in the kernel totals or assume the original 1.0 adapter budget covers the enterprise platform.

On a documented 2-vCPU, 4-GiB Linux runner, the initial benchmark target is p95 cold review at most 30 seconds, warm review at most 5 seconds, and peak RSS at most 512 MiB for a pinned 10,000-file / 128-MiB fixture with at most 200 Python source files, 20 changed Python files and 2,000 changed lines. The remaining files are data/documentation inventory; this is not a latency claim for 10,000 semantic source files. Real repository and adverse-input measurements are required separately. These targets have not been measured. Default safety limits are in the specification.

## Deferred scope

A hosted service and private enterprise deployment are now proposed E10/E11 deliverables; neither is mandatory for offline use. A minimal organization administration interface belongs to those tracks. Billing, a large analytics dashboard, organization graph service, embedding index, continuous background agents, cloud inventory/posture analysis, runtime telemetry, cross-service runtime proof and automatic merge remain deferred. GitHub and Azure Repos Git are explicit platform targets. Other Git platforms and TFVC require separate scope decisions; no platform API is part of E01.

## Planning coverage and implementation status

All E01–E11 now have a scoped specification, execution plan, acceptance criteria and explicit dependency order. The child documents are proposed designs; product implementation and release acceptance are not complete. Historical planning-only requests do not override later human instructions. The coordinator records the current assignment scope and task-specific prerequisites in the [worker dispatch and unblock record](docs/worker-dispatch.md). Every outstanding plan task is now expanded in the [build task board](docs/build-task-board.md) and [declarative registry](docs/build-tasks.json), including bounded design/admission prerequisites and [interface repairs](docs/build-interfaces.md). Local construction, consumed acceptance and activation remain separate.

The observations below describe tracked artifacts at the inspected main revision, not accepted behavior. E04–E06 and E09–E11 now have partial implementation; their earlier “no implementation observed” labels were stale. Additional uncommitted E04/E05/E06/E11 work exists in the local checkout but is not integrated or independently accepted. Full-roadmap acceptance remains pending.

| Package | Specification | Execution plan | Current implementation / acceptance state | Outstanding acceptance |
|---|---|---|---|---|
| E01 | [parent specification, §§5–8](docs/superpowers/specs/2026-10-03-pullraptor-design.md) | [kernel plan](docs/superpowers/plans/2026-10-03-review-kernel.md) | Implemented; acceptance pending | E01-A1–A3 remain unpassed: assertion-body/adverse gaps, mutation/replay equivalence, corpus/user flows, exact benchmark and independent decision; saved suite evidence is a subset at an older candidate |
| E02 | [child spec](docs/superpowers/specs/2026-10-03-e02-snapshots-and-publication.md) | [child plan](docs/superpowers/plans/2026-10-03-e02-snapshots-and-publication.md) | Partial implementation; acceptance pending | PRs #41/#43/#45 integrate publication helpers/local capture; #46 adds publication binding. E02-A1–A4 race/sealing/storage, complete integration/lifecycle, actual hostile CI and usefulness-pilot evidence still require independent acceptance |
| E03 | [child spec](docs/superpowers/specs/2026-10-03-e03-acceptance-completion.md) | [child plan](docs/superpowers/plans/2026-10-03-e03-acceptance-completion.md) | Partial implementation; acceptance pending | Context, transport and conversation modules exist; E03-A1–A3 provenance/consent/injection/real transport limits and independent record remain pending |
| E04 | [child spec](docs/superpowers/specs/2026-10-03-e04-language-workers.md) | [child plan](docs/superpowers/plans/2026-10-03-e04-language-workers.md) | Partial implementation; acceptance pending | Worker protocol module exists; admitted parser inventories, actual language waves/capabilities and E04-A1–A3 evidence remain pending; local admission/graph files are uncommitted |
| E05 | [child spec](docs/superpowers/specs/2026-10-03-e05-security-models.md) | [child plan](docs/superpowers/plans/2026-10-03-e05-security-models.md) | Partial implementation; acceptance pending | Owned IR/lowering/CFG/security-flow and PR #47 SECRET001–003 patterns exist; full E05-A1–A4 independent model/redaction/auth/import evidence remains pending; advisory/import files are uncommitted |
| E06 | [child spec](docs/superpowers/specs/2026-10-03-e06-patches-runner-preferences.md) | [child plan](docs/superpowers/plans/2026-10-03-e06-patches-runner-preferences.md) | Partial implementation; acceptance pending | Patch-precondition module and partial acceptance record exist; E06-A1–A4 corpus/actual isolation/stages/preference acceptance remain pending; local runner/validation/preference work is uncommitted |
| E07 | [child spec](docs/superpowers/specs/2026-10-03-e07-release-distribution.md) | [child plan](docs/superpowers/plans/2026-10-03-e07-release-distribution.md) | Partial implementation; acceptance pending | Candidate wheel builder, provenance helpers and install tests exist; two clean trusted builds, independent origin/bytes and actual clean-platform install evidence remain incomplete; full E07-A1–A3 not accepted |
| E08 | [child spec](docs/superpowers/specs/2026-10-03-e08-delivery-completion.md) | [child plan](docs/superpowers/plans/2026-10-03-e08-delivery-completion.md) | Partial implementation; acceptance pending | Local capture consumer, stdio/MCP session and client metadata artifacts exist; E08-A1–A4 full native editor/plugin/client-session/remote evidence remains pending |
| E09 | [child spec](docs/superpowers/specs/2026-10-03-e09-azure-devops.md) | [child plan](docs/superpowers/plans/2026-10-03-e09-azure-devops.md) | Partial implementation; acceptance pending | Azure acquisition connector and partial record exist; publication/delivery and E09-A1–A3 platform pilot/acceptance remain pending |
| E10 | [child spec](docs/superpowers/specs/2026-10-03-e10-service-api.md) | [child plan](docs/superpowers/plans/2026-10-03-e10-service-api.md) | Partial implementation; acceptance pending | Local API/contracts/jobs/storage modules exist; E10-A1–A4 auth/job/remote app/hosted-private evidence and independent record remain pending |
| E11 | [child spec](docs/superpowers/specs/2026-10-03-e11-enterprise-operations.md) | [child plan](docs/superpowers/plans/2026-10-03-e11-enterprise-operations.md) | Partial implementation; acceptance pending | Identity/authorization/admin stubs exist; E11-A1–A3 actual lifecycle/policy/isolation/retention/operations evidence remains pending; local policy/audit/secret/retention files are uncommitted |

The [planning coverage audit](docs/reviews/2026-10-03-planning-coverage.md) records the inspected base revision and evidence for these states. Existing source and tests demonstrate artifacts are present; they do not independently establish the full exit gates. Historical E03/E08 plans describe earlier subsets; their new completion plans govern outstanding parent scope. The audit is historical; the current revision-bound observations above supersede its file-presence labels. Planning/task checkboxes remain separate from actual evidence. No production code or runtime suite was executed for this refresh.

## Worker execution and completion rules

Use the [execution and acceptance contract](docs/planning-contract.md) and [worker dispatch record](docs/worker-dispatch.md). Before implementation, a worker must identify its exact child task, acceptance IDs, consumed prerequisites, trusted base revision and scope. Verify code and document revisions separately. Missing plan/criteria/consumed prerequisite/isolation means report blocked_for_execution for that task with a resolving owner and next action; do not invent a reduced scope or freeze independent work. Proposed plans make work reviewable, but do not authorize execution or shipment.

Statuses record actual work separately from acceptance. A package becomes Accepted only after all its required criteria have fresh revision-bound artifacts and an independent acceptance decision in `docs/acceptance/E<nn>.md`. E01 has a partial static inventory; no complete independently accepted record is present. Other acceptance paths remain future outputs. A finished subset, passing tests, report hash or checked task box cannot accept an entire roadmap track. Deferred surfaces/capabilities stay visible.

## Acceptance and capability ownership

The [evaluation contract](docs/evaluation.md) remains authoritative for quality, adverse inputs, pilot and benchmark evidence. The [32-row capability catalog](docs/research/2026-10-03-capability-review.md) is reconciled below; IDs express proposed scope, not completion or competitive parity.

| Capability IDs | Owning task / acceptance criterion | Release boundary |
|---|---|---|
| F01, F03, F09, F23, F25, F31 | E01 Tasks 1–8/9; E02-A1/A2 | Exact snapshots, scope, policy, cache equivalence and incomplete recovery |
| F02, F05, F10 | E01 Tasks 3/8; E02-A2/A3/A4 | Exact-line local results and trusted CI/publication lifecycle |
| F04, F06, F11, F24 | E01 Task 8/9; E03-A1/A2/A3 | Deterministic summary, pinned optional context/chat and explicit privacy |
| F07, F08, F16 | E01 Tasks 4/7; E03-A1; E04-A1/A2/A3 | Each language/model tier independently admitted; owned bounded graph presentation |
| F12 | E06-A4 | Explicit maintainer-approved declarative preferences |
| F13, F14, F15 | E03-A3; E06-A1/A2/A3 | Draft suggestions distinct from independently validated patch/execution receipts |
| F17, F18 | E05-A1/A2 | Bounded hazard and authorization models, initially advisory |
| F19, F20, F21 | E05-A3/A4 | Redacted local patterns and provenance-preserving external observations |
| F22 | E01 Tasks 1/8/9; E08-A1; E10-A1 | Canonical JSON/Markdown/SARIF and full/limit-failure consumer compatibility |
| F28 | E06-A3; E08-A1/A2/A3/A4 | Editor/plugin/skill/MCP delivery and declared client/session matrix |
| F30 enterprise portion | E10-A1/A2/A3/A4; E11-A1/A2/A3 | Hosted/private API/app operations and organization controls |
| F32 | E01 Tasks 4/8/9; every child failure policy | Stable capability/cause/trusted recovery; narrowing scope remains explicit |
| F26, F27, F29; F30 cloud-posture portion | Deferred; no implementation task authorized | Queue/routing, post-merge automation, runtime telemetry and cloud posture |
| Delivery amendments beyond catalog | E07-A1/A2/A3; E09-A1/A2/A3; E10/E11 criteria | Packaging, Azure integration and service/operations have separate budgets/evidence |

## Delivery sequence and release acceptance

1. Audit and independently accept existing E01 work using Task 9; accept E07 packaging/provenance/install evidence.
2. Complete/accept E02A local capture, then E02B hostile CI/publication. Run the E01/E02 usefulness pilot with thresholds declared before collection.
3. Finish E03 acceptance and E08 local editor/plugin/MCP delivery. They remain optional to deterministic CLI review; E03 consent/transport gates precede remote AI.
4. After the usefulness gate, admit E04 languages/capabilities and E05 modeled security independently; E06 patch/runner/preferences only under its isolation gate. No release requires unsupported languages to appear complete.
5. E09 may use accepted customer CI without hosting. Start E10-A1/A2 local API/job contracts, then accept E11-A1/A2 identity/policy/isolation/retention essentials, then E10-A3/A4 remote app/deployment pilots and E08-A4 remote MCP. Finish E11-A3 operational acceptance before enterprise-ready claims.
6. Release only the accepted subsets/languages/platforms; publish versioned artifact support/limitation and acceptance records. Actual external release is a separately authorized action.

Each child spec declares proposed dependency/resource budgets and failure policy. Measure and inventory them before admission; the original kernel budgets do not cover enterprise operations. Platform/client/version selections remain proposed until pinned and exercised. Independent review must accept the actual source/artifact revision and complete requested user flow, not a graph or status label.

## Beta 0.1.x release milestone

The [release readiness plan](docs/superpowers/plans/2026-10-05-beta-release-readiness.md) and [18-card release queue](docs/release-tasks.json) add the missing end-to-end release work. They supplement, rather than replace, the 71 historical E01–E11 build cards. A maintainer scope decision is required by BR-01 before implementation: the proposed first milestone is an offline wheel-installed Python 3.12 CLI beta with generic diff, advisory PY001–PY003 and exact committed Git revisions. Supported artifact/platform/command claims derive only from accepted evidence. All other roadmap goals remain owned; no package is silently removed.

Released package metadata on the tag is `0.1.0b1` (human label beta 0.1.x). Editor client metadata may still read `0.3.0` until E08 delivery tracks align versions; that is not release evidence for the wheel. BR-01–BR-17 for the first beta are recorded in `docs/releases/beta-0.1-decisions.md` and the release manifest. Full E01 assertion-map reconciliation and complete E07 container/update/rollback acceptance remain future work; the beta subset does not claim them.

| Phase | Required tasks | Exit gate / state |
|---|---|---|
| Scope and evidence | BR-01–02 | Approved commands/rules/artifacts/platforms/version/owners and fresh obligation-to-evidence map |
| Kernel completion | BR-03–06; E01-T9-RECORDS/OUTPUT/CACHE/CORPUS/BENCH | Required adverse, determinism/equivalence, licensed corpus/user flows, 10k-file benchmark and measured budgets |
| Independent kernel decision | BR-07; E01-T9-ACCEPT | E01-A1–A3 complete passed evidence and independent acceptance |
| Artifact preparation | BR-08–11; E07 inventory/build/provenance/install cards | Every shipped entry point inventoried with owned pending admission or verified containment, pinned licenses/build tools, two reproducible builds, independent origin/bytes, actual clean install/parity and truthful docs |
| Independent release verification | BR-12–14 | Required candidate checks/risk review, accepted E07 beta subset, all enabled conditional capability decisions and frozen candidate dossier; ready_for_release |
| Human release decision | BR-15 | Exact candidate/artifacts/destinations receive maintainer go/no-go and separate publication authorization |
| Publication and customer verification | BR-16–17 | Immutable approved assets published; downloaded installation/review verified; release record and this plan updated from actual receipts |
| Subsequent beta maintenance | BR-18 (conditional) | Update/interrupted-update/rollback tested against the independently accepted prior artifact before those claims or the next patch release |

Ready for release is distinct from published and verified. A first wheel-only beta may independently accept an E07 scoped subset while the full container/update/rollback package remains partial. No date is currently committed: BR-01/02 must identify owners, environment availability, remaining estimates and review windows before forecasting. Missing evidence remains a blocker for its consuming operation; deadline pressure cannot grant acceptance.

If staged/workdir input is included, independently accept E02-A1. If GitHub CI/publication is included, complete the consumed E02 criteria, actual same-repository/fork isolation, publication reconciliation and the E01/E02 usefulness pilot (at least 30 eligible Python PRs across three repositories with two maintainers and predeclared noise/time thresholds). The full [evaluation contract](docs/evaluation.md) still gates wider breadth and default defect blocking. Container, AI, language/security, patches/runner, editor/MCP, Azure and hosted/enterprise capabilities consume their own child acceptance gates as listed in the release plan. At final release admission, even excluded-from-marketing commands bundled in an artifact must be independently accepted for their exposed scope or demonstrably disabled. BR-08 inventories pending criteria for bounded construction; BR-14 consumes final acceptance. Candidate build/install cannot depend on their own future acceptance; activation/remote/runner gates remain separate.

## Next concrete action

Post-0.1.0b1 construction (see [worker dispatch](docs/worker-dispatch.md)): (1) keep customer docs aligned with the release manifest; (2) close `E02-T2-BIND` fixtures/evidence and implement `E02-T2-INTEGRATE` publisher paths without enabling customer publish; (3) continue E01 Task 9 and BR-02 evidence rebaseline in parallel; (4) open `0.1.0b2` only under [beta-0.1.0b2-entry-criteria.md](docs/releases/beta-0.1.0b2-entry-criteria.md) when triggered. PR #46 merged the publication binding validator; remaining E02 lifecycle, CI template, and usefulness-pilot evidence are separate cards.

The [build registry](docs/build-tasks.json) remains the immutable historical construction contract at its original base; re-pin source/doc/trusted-base revisions per dispatch. Follow the [updated board](docs/build-task-board.md), [worker handoff](docs/worker-dispatch.md) and release queue. Independent review findings create owned corrections, never product acceptance. Deferred scope stays deferred; no blanket missing-child-plan blocker applies.
