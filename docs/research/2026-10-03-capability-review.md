# Review capability study

Study date: 2026-10-03. This document translates market research into independent product requirements. Named comparisons and vendor URLs remain in the originating conversation to preserve the project's naming constraint.

## Method and limits

The study read current primary documentation for representative hosted PR reviewers, configurable open-source review automation, developer security scanners, a telemetry-informed reviewer, and a code-to-cloud security platform. Selection favored direct PR integration, documented workflow depth, deployment choices, and distinct context sources. It did not establish an objective top ranking, run products, benchmark detection quality, validate billing, or inspect proprietary engines.

Documented capabilities are evidence of advertised product behavior, not measured precision, recall, complete reachability, sound proofs, or guaranteed fixes. Current primary docs describe specialized agents, repository exploration, contextual memory, revision snapshots, security impact views, and remediation workflows. Those mechanisms by themselves would not establish a distinctive design here.

## Findings that affect the plan

- Modern PR review is a workflow: summaries, incremental feedback, exact-line findings, context, conversation, suggestions, configuration, and finding lifecycle matter together.
- Full-repository access does not imply exhaustive analysis. Depth, exclusions, unresolved calls, framework behavior, and resource caps affect coverage.
- Security scanners, general review agents, and runtime/cloud platforms overlap but answer different questions. Runtime-derived context can enrich a PR review; it is still an additional system to operate.
- A locally installed CLI may use remote processing. Self-hosted application code may still call remote models. Offline operation must be tested separately.
- A generated patch can be delivered despite failed verification in existing workflows. PullRaptor should preserve draft usefulness while making validation failure unmistakable.
- Review snapshots and evidence graphs already exist in modern tools. PullRaptor's proposed distinction is a compact, inspectable differential-analysis contract with exact cache inputs, explicit incompleteness, and independently evaluated decision thresholds.
- Learning from reactions is not calibration: accepted comments may still be wrong, and useful comments may remain unfixed.
- Broad analyzer bundles have dependency, licensing, startup, and maintenance costs. Stable result import is usually smaller than bundling every engine.
- Privacy claims require concrete data-flow and retention definitions. The offline kernel should not inherit assumptions from optional provider modes.

## Capability acceptance catalog

Every row is proposed. “Included” means a 1.0 target with the stated boundary; none is implemented. E01–E06 refer to the master plan.

| ID | Capability | Package | 1.0 scope and acceptance boundary |
|---|---|---|---|
| F01 | Local branch/diff review | E01/E02 | Committed revisions first; staged/unstaged immutable manifests next; untracked files explicitly opt in |
| F02 | Automatic/manual PR review | E02 | GitHub event/manual triggers; no persistent hosted bot required |
| F03 | Incremental repeat review | E01/E02 | Cache reuse and stable lifecycle; same semantic result as a clean run |
| F04 | Summary and walkthrough | E01/E03 | Deterministic facts first; optional prose may not invent behavior |
| F05 | Inline actionable findings | E01/E02 | Local exact spans first; platform inline locations validated against the published commit |
| F06 | Issue/requirement context | E03 | Explicit pinned issue content; requirement checks advisory unless a executable contract exists |
| F07 | Repository/cross-file and CI context | E01/E03/E04 | Resolved source first; exact-head CI failure logs later, size/redaction limits; no universal repository understanding |
| F08 | Grouped changes and impact diagrams | E03/E04 | Graph-derived groups, source links, bounded Mermaid; possible impact labeled as such |
| F09 | Repository/path rules | E01/E02 | Declarative base-owned TOML; explicit precedence and audit of applied policy |
| F10 | Noise, draft, and path controls | E01/E02 | Visible exclusions; comment caps move findings to summary rather than erase them |
| F11 | Conversation and challenges | E03 | Snapshot-grounded answers with evidence links and visible uncertainty |
| F12 | Preference learning | E06 | Proposals require maintainer acceptance; source and scope retained; no silent policy relaxation |
| F13 | Test/docstring suggestions | E03/E06 | Optional drafts; generated is distinct from executed or behaviorally adequate |
| F14 | Suggested patches | E03/E06 | Narrow scoped diff with base/head preconditions; no automatic merge |
| F15 | Regression-based patch validation | E06 | Isolated execution, failing baseline reproduction where possible, passing post-patch checks |
| F16 | Multiple language tiers | E01/E04 | Python first; named syntax and analysis capabilities separately tested for every adapter |
| F17 | Source-to-sink security paths | E05 | Finite, declared models and unresolved boundary reporting; no all-paths claim |
| F18 | Authorization/trust checks | E05 | Principal/action/resource obligations with assumption receipts; initially advisory |
| F19 | Secret-risk detection | E05 | Local patterns/entropy/context; redact values; no remote secret-validity probe |
| F20 | Dependency advisory review | E05 | Supported lockfile versions + optional advisory source with freshness; no inference of runtime exploitability |
| F21 | External scanner result import | E05 | Explicit SARIF 2.1.0 subset, producer/version/revision provenance, untrusted input limits |
| F22 | Machine-readable output | E01 | JSON, Markdown and SARIF 2.1.0; export does not require platform code-scanning eligibility |
| F23 | Review/time/context budgets | E01/E03 | Deterministic resource limits and optional AI request/output caps; partial analysis explicit |
| F24 | Offline and privacy controls | E01/E03 | Zero core egress; explicit provider consent/configuration, context preview and retention policy |
| F25 | Revision-bound receipts | E01 | Exact input manifests and independently checkable locations; hashes do not establish truth |
| F26 | Reviewer routing and PR queue | Deferred | Requires organizational history/dashboard; ownership hints alone do not deliver the full capability |
| F27 | Post-merge and release automation | Deferred | Separate permissions and workflow scope |
| F28 | Agent/editor access | E06/E08 | Shared review contract; E08 owns VS Code and neutral editor/assistant plugins, MCP and skills after per-client protocol review |
| F29 | Production telemetry correlation | Deferred | Requires a runtime ingestion/retention system |
| F30 | Cloud posture and enterprise control plane | Split: E10/E11 enterprise delivery; posture deferred | Hosted/private service and enterprise governance now requested; cloud infrastructure posture analysis remains deferred |
| F31 | Independently verified review scope | E01/E02 | Coordinator-owned pinned request; missing/foreign/duplicate receipts cannot establish completeness or publication eligibility |
| F32 | Actionable incomplete-review guidance | E01–E06 | Stable cause, affected capability and trusted next action; narrowing scope remains explicit and never fabricates a clean result |

The original study defined F01–F30. F31–F32 were added by the [independent security/architecture review](../reviews/2026-10-03-security-architecture.md); they are product requirements, not newly advertised market capabilities. The original 28 included targets count workflow capabilities, not equal detection strength. The user-requested E07–E11 delivery expansion is recorded in the [master plan](../../Master-Plan.md); the partial promotion of F30 does not claim its full cloud-posture capability or alter the historical 1.0 count. Deep security, enterprise management, and comprehensive language semantics cannot be squeezed into a zero-dependency first release. Feature claims must include scope and be checked against [evaluation requirements](../evaluation.md).

| Intended delivery class | Capability IDs | Required interpretation |
|---|---|---|
| End-to-end workflow | F01–F05, F09–F12, F22–F25, F28, F31–F32 | Complete the named user flow with its stated scope |
| Advisory draft | F06, F13, F14, F18 | Useful proposal or obligation question; not a verified correctness claim |
| Language/model conditional | F07, F08, F15–F17, F19 | Supported inputs only; limitations and missing evidence visible |
| Import-based | F20, F21 | External data with provenance; imported accuracy is not native validation |

This classification is more important than the count. F15 needs an isolated check execution receipt; only an actual failing-baseline/passing-patch reproduction can claim the observed regression was resolved.

## Provenance available inside the project

Neutral implementation references can be retained here without competing product names:

- [Python AST reference](https://docs.python.org/3.12/library/ast.html): grammar and source locations; parsing is not scoping/type checking and complex input can exhaust resources.
- [Git diff reference](https://git-scm.com/docs/git-diff): merge-base comparison and machine-readable file status modes.
- [GitHub review API](https://docs.github.com/en/rest/pulls/reviews): commit-bound review publication and permissions.
- [GitHub workflow security](https://securitylab.github.com/resources/github-actions-preventing-pwn-requests/): separation of untrusted PR processing and privileged publication.
- [SARIF platform support](https://docs.github.com/en/code-security/reference/code-scanning/sarif-files/sarif-support): supported 2.1.0 subset, fingerprints, and account eligibility.
- [Abstract interpretation foundations](https://www.di.ens.fr/~cousot/COUSOTpapers/POPL77.shtml): lattice/fixpoint foundations. PullRaptor's bounded models still require their own correctness argument.

Source pages can change. Implementation must pin API behavior, parser/runtime versions, rule versions, fixtures, and advisory timestamps. No third-party source code or rule corpus was imported during this planning task.
