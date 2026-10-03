# PullRaptor Master Plan

Date: 2026-10-03. Status: proposed design and implementation plan. External distribution and enterprise integration scope is recorded in the roadmap; detailed child designs and implementation remain subject to review. These planning amendments do not establish a working reviewer or accepted release.

## Intended outcome

Build a practical PR reviewer whose core user flows remain understandable under incomplete analysis and hostile input, expressed through a small mathematical kernel. Accuracy, defensible evidence, and safe operation take priority over nominal feature count. Deliver broad workflow value through conditional adapters after the core demonstrates usefulness. Keep code, dependencies, installation, and operations small. Keep competing product names out of all project files.

The initial recommendation was local CLI plus GitHub CI, optional AI, and developer/team use. The expanded delivery roadmap covers packaged CLI/container, VS Code extension, repository app, CI integration, review API/SDK, hosted service, private enterprise deployment, AI-editor and terminal-assistant plugins/MCP/skills, and Azure DevOps. Customers must be able to install or connect released artifacts without manually cloning PullRaptor or embedding its source in their own application. Named client selections and references remain in the originating conversation; project records use neutral adapter roles. Generic cloud execution is covered separately by hosted deployment and cloud-session compatibility gates. These are roadmap deliverables, not implemented capabilities. The first semantic target is Python because its parser is available in the chosen runtime. The language choice is an assumption for review, not a user-confirmed preference.

## Decision record

| Decision | Proposed choice | Reason / consequence |
|---|---|---|
| Core runtime | Python 3.12.x only initially; additional minor versions need compatibility tests | Short implementation, built-in AST, TOML, hashing, subprocess, JSON |
| Runtime dependencies | Zero third-party packages in the deterministic kernel; Git executable required | No mandatory model SDK, graph database, vector service, web framework, or container |
| Distribution | Versioned packaged CLI and container, editor/plugin packages, and service connections; source checkout is a development path | No manual PullRaptor clone for customers; declare Python/Git or bundled runtime requirements; review build dependencies and licenses |
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

Each package needs its own child specification, implementation plan and acceptance review. Only E01 currently has a detailed execution plan. E07–E11 expand the requested roadmap beyond the original kernel-focused 1.0 scope; they are decomposed delivery tracks, not promised dates or a claim that the original budgets cover a hosted platform.

| Package | Target | Deliverable | Exit gate | Status |
|---|---|---|---|---|
| E01 | 0.1 | Offline kernel, Python patterns, diff summaries, request/scope receipts, actionable coverage diagnostics, bounded JSON/Markdown/SARIF, private cache | Determinism, clean/incremental equivalence, trusted cache admission, bounded ingestion, independent scope validation | Complete |
| E02 | 0.2 | Two child packages: immutable staged/unstaged snapshots; hardened GitHub CI/publication, stable lifecycle, draft/path controls | Snapshot races; disposable fork isolation, current head/base/policy/scope binding, retry reconciliation, publish preview | Proposed |
| E03 | 0.3 | Optional AI review/chat, pinned issue and CI-failure context, explanations, test/doc suggestions | Typed untrusted proposals, approved transport, prompt-injection cases, bounded cost, no AI-only blockers | Proposed |
| E04 | 0.4 | Optional language workers; start JS/TS and Go, then Java/C#, then Rust/PHP/Ruby/C/C++ | Per-language capability matrix and held-out quality gate; syntax support is not dataflow support | Proposed |
| E05 | 0.5 | Bounded source-to-sink analysis, authorization obligations, local secret patterns, lockfile advisories, scanner import | Explicit assumptions, taint and sanitizer negatives, redaction, no unsound unreachable suppression | Proposed |
| E06 | 1.0 | Patch validation, isolated regression runner, reviewed preferences; shared contracts for editor/agent consumers | Patch preconditions, actual execution receipts, clean re-analysis, feature acceptance audit; install/editor deliverables owned by E07/E08 | Proposed |
| E07 | Distribution track | Packaged CLI, pinned container, release provenance, update/rollback and offline installation | Clean-machine install without manual source clone; runtime/license inventory, provenance verification, uninstall/rollback, artifact review equivalence | Proposed |
| E08 | Editor/agent track | VS Code extension; AI-editor and terminal-assistant plugin packages; standalone skills and local/remote MCP adapter | Per-client/version/session matrix, credential isolation, bounded protocol, stale snapshot handling, safe rendering and no unauthorized writes | Proposed |
| E09 | Azure DevOps track | Azure Repos Git connector, Azure Pipelines template/task, service hooks, PR comments/status and organization extension packaging | Trusted-policy isolation, iteration/head/base binding, event retry reconciliation, branch-policy mapping and scoped credentials | Proposed |
| E10 | Service track | Versioned review API, thin SDK, authenticated completion webhooks, GitHub App, hosted and private enterprise deployments | API compatibility, repository authorization, job/tenant isolation, source-transfer/retention enforcement, webhook replay tests and failure recovery | Proposed |
| E11 | Enterprise operations track | SSO, role-based access, organization policy, audit, secrets, deployment administration and controlled releases | Cross-tenant denial, revocation, policy provenance, deletion/backup recovery, update rollback and operational pilot | Proposed |

Target numbers express order and intended scope, not completion dates. E04 can add grammars in parallel, but each claimed analysis capability must earn its own release evidence. E05 initially covers narrow modeled Python flows; other languages remain explicit gaps until evaluated.

## Breadth without a large core

The original amended capability catalog has 32 items: 30 from the workflow study plus two from independent security/architecture review. Its kernel-focused 1.0 proposal includes 28. Enterprise delivery and governance, previously deferred within cloud/enterprise posture, are now requested through E07–E11. Reviewer/queue management, post-merge automation, runtime telemetry and cloud infrastructure posture analysis remain deferred. Delivery tracks are not extra detector capabilities and do not change the historical 28-of-32 count; reconcile the capability catalog in their child designs. That is an internal unweighted planning checklist, not measured parity with any product. Conditional language and security capabilities cannot be checked off merely because a command exists.

Six indispensable user flows govern 1.0 for demonstrated language/model tiers: local review, repeat review after a push, clear summary, actionable exact-line findings, explain/challenge a finding, and propose a patch with truthful validation status. These must all work end to end. Each flow also explains incomplete coverage and a trusted recovery action. More checkboxes cannot compensate for a broken core flow.

## External delivery and enterprise adoption

The same deterministic kernel produces a revision-bound report in every deployment. Network/authentication, job coordination, platform publication, AI providers and UI adapters remain outside it. Skills explain a workflow; MCP exposes bounded tools; plugins package those components; an editor extension supplies native presentation. None substitutes for the review engine or validates model-generated claims by itself.

| Surface | Customer experience | Delivery owner and acceptance scope |
|---|---|---|
| Packaged CLI/container | Install a published release or pull a pinned image; review locally or in their runner | E07; support matrix, explicit runtime prerequisites and no source-checkout requirement |
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

Every delivery track first writes its own child design, dependency/license inventory, compatibility matrix, failure policy, resource budget and meaningful adverse acceptance cases. Validate an install → authenticate/connect → review exact revisions → display coverage → repeat after changes → revoke/uninstall flow on each supported surface. Compare completed canonical reports against the packaged CLI for identical logical inputs. Pin and test transport/client/platform versions; packaging portability does not establish behavior portability. Test changed policy with unchanged head, cross-repository replay, duplicate events, expired tokens, malicious report rendering, tenant-crossing access and interrupted jobs. All tracks remain Proposed until their own evidence exists.

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

## Next concrete action

Review [the specification](docs/superpowers/specs/2026-10-03-pullraptor-design.md), [security and architecture decisions](docs/reviews/2026-10-03-security-architecture.md), and [the E01 plan](docs/superpowers/plans/2026-10-03-review-kernel.md). If implementation is subsequently authorized, build E01 and measure its limits before expanding delivery or analysis claims. Then write scoped E07–E11 child designs/plans in dependency order; the requested integration scope does not authorize production implementation.
