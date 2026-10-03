# Security and architecture review decisions

Date: 2026-10-03. Status: proposed planning amendments. No product implementation, exploit reproduction, product tests or performance measurements were performed.

## Review basis and personas

The baseline is Git commit `cfa0e3dc5e471c319f40dccfdbf26e359c358667`. Reviewers read README, AGENTS, master plan, capability study, specification, mathematical core, evaluation contract and E01 child plan. Baseline content is recoverable with `git show <commit>:<path>`; this record describes the resulting amendments rather than silently replacing the original decision history.

Three independent subagents used the portable [researcher](../personas/researcher.md) and [reviewer](../personas/reviewer.md) prompts:

| Assignment | Persona | Purpose |
|---|---|---|
| Security researcher | Researcher | Verify practical controls in primary documentation and assess dependency/operation cost |
| Security reviewer | Reviewer | Construct attack scenarios across process, cache, record, renderer, AI and publisher boundaries |
| Architecture reviewer | Reviewer | Challenge scope, types, dataflow, determinism, lifecycle and product commitments |

The personas are reusable instructions passed to collaboration subagents. They do not install/register platform agents or add runtime dependencies. Subagents made recommendations; the coordinating review checked them against the saved design before editing. Finding priorities below express plan risk if omitted, not discovered vulnerabilities in running software.

## Adopted decisions

| ID / priority | Gap and concrete counterexample | Smallest adopted change | Owner / acceptance evidence |
|---|---|---|---|
| R01 / P1 | Worker omits an unsupported changed file; all returned receipts say complete | Coordinator-owned pinned ReviewContract, append-only import discovery, sealed expected scope and receipt bijection | E01 Tasks 1/6/7; omitted/duplicate/foreign/wrong-revision receipt and scope-expansion fixtures |
| R02 / P1 | Valid cached JSON deletes a mutation fact; a warm run misses a real pattern | Private operator-owned cache only; foreign/shared/restored entries ignored; CI defaults off; no-follow ownership/permission checks | E01 Task 7 and E02 deployment; forged-fact/redirect/unsafe-permission tests and completed clean equivalence |
| R03 / P1 | Huge changed text or a stalled Git process bypasses source-only limits | One absolute deadline, streamed bounded stdout/stderr and admitted-text limits on every subprocess; kill/reap | E01 Task 3; text/output flood, stalled process, deadline and process-tree tests |
| R04 / P1 | Partial-clone Git fetches implicitly; ambient startup/config/handles expose authority | Required Git capability probes, option-safe refs, disabled lazy fetch/replacement/helpers, trusted executable, allowlisted environment, closed handles and parser `-I -S` | E01 Tasks 3/4; missing promisor objects, startup/config/credential/handle sentinel tests |
| R05 / P1 | Duplicate revision keys or nested/flooded JSON undermine strict records | One bounded stdlib decoder with duplicate/nonfinite/UTF-8/type/range/depth/item/string checks and bounded pipes | E01 Tasks 1/3; boundary and malformed protocol cases; reused by later adapters |
| R06 / P1 | Source path/claim contains terminal controls or Markdown link/fence breakout | Separate safe literal rendering, visible controls/directional text, trusted-only navigation links | E01 Task 8/E02 publisher; terminal/Markdown/SARIF hostile presentation tests |
| R07 / P1 | Head is unchanged while base policy advances, or another PR shares the head | Platform-derived artifact/repository/PR/workflow/run association plus fresh base/head/policy/scope/reviewer binding | E02 child plan required; cross-PR replay, moved base, stale policy/scope and wrong-origin tests |
| R08 / P2 | Content cache requires a path, and resolved facts share the cached type | ContentFacts, BoundFacts and run-local ResolvedFacts; digest all fact-producing components; cache controls outside semantic identity | E01 Tasks 1/4/7; same blob on multiple paths/sides, renamed occurrence, changed extractor and canonical equality |
| R09 / P2 | Sanitizing `b` mistakenly clears hazards on original `a`; disconnected auth node retains top | Finite location-to-hazard environments with source/value/alias rules; incomplete entry/CFG cannot establish authorization | E05 child spec prerequisite; sanitizer-original-value, alias, cycle and alternate-entry fixtures |
| R10 / P2 | A branch finding remains newly detected against merge base on every push | Stable repository/PR/rule/obligation lifecycle key separate from revision observations, evidence and dismissal; reconcile ambiguous POST | E02; repeated pushes, changed witness, dismissal, rename and duplicate-event cases |
| R11 / P2 | Model/import JSON fabricates supported/permission/configuration fields | Distinct untrusted Proposal type; validators alone create precise evidence; approved provider origin/path with tested transport policy | E03/E05; forged authority fields, injection, proxy/redirect/address/credential tests |
| R12 / P1 | Workflow setup exposes persisted checkout credentials or executes head-derived installation | One hardened template: full action pins, minimal permissions, no persisted checkout credentials, trusted reviewer outside head, PR text as data; disposable isolated analysis | E02; template audit plus fork/secret/egress/filesystem tests; publisher never checks out head or restores analysis-controlled caches |
| R13 / P1 | Stdlib import either always makes scope incomplete or gets undocumented symbol authority | Classify repository/model-external/unresolved imports; pin stdlib identities and narrow subprocess symbols, preserve local shadowing/ambiguity | E01 Task 4; stdlib, subprocess aliases, local module, ambiguous candidates and missing external target |
| R14 / P1 | Oversized/full-timeout report cannot satisfy its own schema or receive the remaining deadline | Strict full/limit-failure union, exact item accounting, explicit renderer deadline/limits and fixed reserve inside total budget | E01 Tasks 1/2/7/8; byte/item/work-cutoff exhaustion and minimum-capacity cases in every format |
| R15 / P2 | A validated filename containing `?`, `#` or `%` changes link resolution | Owned fixed-origin URI builder with encoded path segments/escaped labels; owned diagram serializer before activation | E01 Task 8 and E03/E04; reserved-character path round trips and diagram-label breakout |
| R16 / P2 | Two missing modules from one file collide, or unfinished discovery appears complete | Distinct file/lookup scope keys and coordinator discovery-completion predicate | E01 Tasks 1/6/7; resolve x while y remains missing; known receipts complete with unfinished discovery still exit 2 |

These decisions are integrated into the [security and architecture contract](../security-architecture.md), [specification](../superpowers/specs/2026-10-03-pullraptor-design.md), [mathematical core](../mathematical-core.md), [evaluation gates](../evaluation.md) and [E01 task interfaces](../superpowers/plans/2026-10-03-review-kernel.md).

## Scope and goal amendments

Add F31, independently verified scope, and F32, actionable incomplete-review guidance, to the existing catalog. A gap must identify its affected capability, stable cause and a trusted recovery action. A valid local finding can survive unrelated partial analysis; the overall review remains incomplete. Missing baseline analysis prevents causal introduced/fixed claims.

The amended catalog has 32 rows, originally with 28 conditional included targets and four deferred. Concurrent roadmap additions introduce separate delivery tracks and promote the enterprise-delivery part of F30 while retaining deferred cloud-posture analysis. This security review preserves those additions; their child designs still need independent review. The core commitment centers on six complete user flows for demonstrated tiers. Language/security breadth follows capability evidence and an E01/E02 pilot: at least 30 eligible PRs, three repositories and two maintainers, with tolerable noise/time thresholds agreed before collection. These pilot minima assess feasibility, not statistical correctness.

Keep the stdlib kernel and existing budgets. E01 adds one shared process module, raising the proposed map from 13 to 14 modules. Record/type checks, codec, safe rendering and cache admission stay in existing modules. No third-party runtime package, daemon, graph store, web service or mandatory container is added to trusted local operation. Hostile CI still needs a separately measured deployment isolation boundary.

## Choices deliberately deferred

- Authenticate foreign caches with signatures/key management only if a later measured deployment need justifies it; re-extraction or no cache is simpler now.
- Do not promise same-user filesystem isolation from Python flags or environment filtering. Support hostile analysis only where its actual deployment controls are enforced.
- Do not add a general-purpose sandbox/orchestration framework or managed egress service to the kernel. E02/E03 must choose and test concrete platform/transport controls before activation.
- Do not add new security detector breadth as a substitute for trust-boundary correctness. E05 still requires a child specification and held-out evidence.

## Primary evidence

Sources were checked on 2026-10-03. They establish mechanisms and documented defaults, not correctness of a future PullRaptor implementation.

- [Git command controls](https://git-scm.com/docs/git) and [revision verification](https://git-scm.com/docs/git-rev-parse): explicit no-lazy-fetch/replacement controls and option-safe ref resolution. Required behavior is probed rather than assuming every installed Git supports it.
- [Python JSON](https://docs.python.org/3.12/library/json.html): decoder defaults permit duplicate names and nonfinite numbers; application-specific resource/schema bounds remain necessary.
- [Python subprocess](https://docs.python.org/3.12/library/subprocess.html) and [interpreter startup](https://docs.python.org/3.12/using/cmdline.html): supplied environments, inherited handles, absolute executable paths and isolated/no-site startup controls have distinct effects; none supplies a host filesystem sandbox.
- [Python standard-library identities](https://docs.python.org/3.12/library/sys.html#sys.stdlib_module_names): the set lists top-level names, including unavailable/disabled modules; it is not a symbol table or proof of a successful import. The planned external model remains narrower.
- [Python HTTP handling](https://docs.python.org/3.12/library/urllib.request.html) and [SSRF prevention guidance](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html): redirects, proxies and destination validation require an explicit transport policy, including address changes. E03's exact implementation is not selected yet.
- [Workflow security](https://docs.github.com/en/actions/reference/security/secure-use), [checkout credentials](https://github.com/actions/checkout), [cache access boundaries](https://docs.github.com/en/actions/reference/workflows-and-actions/dependency-caching) and [temporary-file handling](https://docs.python.org/3.12/library/tempfile.html): support least authority, isolated untrusted processing and protected disposable storage decisions.

## Remaining limitations

This assessment challenged a proposed design, not running code. Passing documentation checks confirms consistency/links/naming only. E01 still needs implementation and actual adverse-input testing. E02–E06 still need scoped child plans, platform/transport/OS compatibility decisions and acceptance evidence. Resource targets and usefulness/accuracy gates are unmeasured. Runtime vulnerabilities or a compromised trusted host remain outside the stated controls.

Concurrent source/test files appeared while this documentation review was finishing. They were preserved and are outside this assessment; this review did not implement or verify them. Artifact status and roadmap counts are recorded separately from accepted software capability.

Both reviewers independently re-read the amended contracts. Their second-pass gaps about external imports, failure-schema/deadline propagation, lookup identity and URI encoding led to R13–R16 above. Follow-up review confirmed those corrections; a remaining slow-bootstrap/shorter-policy corner was closed by bounding preparation to the minimum admitted work duration, while retaining the original invocation start. Minimum envelope depth/string capacity and typed serialization failure also keep caller exit status explicit. Review is additional design evidence; it does not validate runtime enforcement.

## Documentation validation

The final local audit checked 12 Markdown documents, 35 local links, balanced code fences, ordered unique F01–F32 capability IDs, and eight E01 tasks with 56 unchecked steps. The deferred split preserves F26/F27/F29 and cloud posture within F30; the historical kernel-focused count remains 28 of 32. Stale fact types/checkout assumptions were absent. The naming scan covered project Markdown/Python text, and `git diff --check` passed. Named editor/assistant references in concurrent roadmap additions were changed to neutral roles while preserving delivery scope. These checks validate the planning artifacts only; concurrent product code/tests were not executed or assessed.
