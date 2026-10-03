# PullRaptor product and architecture specification

Date: 2026-10-03. Status: proposed product direction. Scoped specifications/plans now cover E01–E11 through the master-plan index. Existing code and historical checked tasks do not establish full release acceptance. No implementation is authorized by task checkboxes or this document alone.

## 1. Product purpose

Help a developer or reviewer understand a change, find defensible problems, ask about the reasoning, and prepare a reviewable correction without operating a large service stack. Combine a useful PR workflow with local deterministic analysis and optional deeper reasoning. The user asked for broad modern features, mathematical rigor, minimal code/dependencies, independent design, and no competing names in project files. The user delegated selection of the best deployment combination after research.

Success requires evidence that the six core review flows improve decisions for demonstrated tiers at a tolerable noise, time, and resource cost, including when source is hostile or requested analysis is incomplete. A larger feature list is insufficient. Run an E01/E02 usefulness pilot before expanding language/security breadth. Do not claim superior accuracy, mathematical proof of arbitrary code, or exhaustive vulnerability detection.

## 2. Approaches considered

| Approach | Strength | Cost / limitation | Decision |
|---|---|---|---|
| Deterministic local kernel plus optional adapters | Reproducible, cheap, inspectable, offline base; reusable in CI | Narrow initial semantic coverage; AI features arrive later | Recommended |
| Hosted AI-first reviewer | Broad natural-language reasoning and convenient PR interaction | Service operations, credentials, source transfer, variable cost/results | Optional deployment later |
| Full analyzer/agent platform | Extensive tool and language breadth | Large dependencies, orchestration, licenses, resource requirements | Reject as core architecture |

For runtime, Python wins the first stage on authored-code simplicity and its built-in parser. Go is a good alternative if a compiled executable and Go-first analysis become more important than Python coverage. Rust would add implementation and packaging work without a demonstrated requirement. This recommendation is a design judgment; no comparative benchmark was run.

## 3. User flows

1. **Review locally:** choose base and head; receive a concise summary, newly detected findings, surviving baseline findings, and an explicit coverage section. No network or source execution.
2. **Review a PR:** CI analyzes the immutable PR revision; a separate publisher previews/posts a summary and up to ten new inline comments. Old findings remain linked to their original revision; repeats update lifecycle rather than spam.
3. **Explain or challenge:** later chat answers from the pinned report, source, and provided context. Each conversation stays bound to that report/head/context manifest; answers about later code require a new snapshot. A conflicting observation adds counterevidence or requests a new run. Dismissing a thread is feedback, not proof of a fix.
4. **Prepare a correction:** later patch generation returns a scoped diff and validation receipt. A draft can remain useful after failed verification, but must say failed or not run. Passing syntax/build checks is distinct from reproducing and correcting a baseline regression. Publish/commit is an explicit action; merge is outside the reviewer.

The source-level reports must be useful without diagrams, AI, a dashboard, or a platform account. Diagrams are optional bounded presentations of the same graph facts. Grouped changes show the edge/reason for grouping and distinguish dependency edges from presentation order. Missing edges mean impact was not established, not that impact is absent. Cycles/unknown edges fall back to a file walkthrough.

## 4. Core pipeline and boundaries

```mermaid
flowchart LR
  A[Explicit base and head] --> B[Immutable Git blobs]
  B --> C[Diff and capability inventory]
  C --> S[Coordinator-owned request and scope]
  S --> D[Language facts and optional workers]
  D --> E[Differential findings and evidence]
  D --> J[Validate receipts against expected scope]
  J --> F[Independent policy evaluation]
  E --> F
  F --> G[Local JSON Markdown SARIF]
  E --> H[Optional bounded AI proposals]
  H --> F
  G --> I[Separate validated publisher]
```

The kernel transforms immutable records. Snapshot reading, optional cache I/O, provider calls, publication, and execution workers are separate boundaries. The coordinator owns expected scope and checks independent worker receipts. AI/imports return distinct untrusted `Proposal` records; only trusted validators construct evidence for the exact predicate they check. Graph/context records do not become policy instructions. Apply the detailed [security and architecture contract](../../security-architecture.md).

Initial files are mapped in the child plan. Avoid generic plugin containers, inheritance-heavy frameworks, event buses, a server, and premature database abstractions. Keep simple functions with explicit input/output records. The optional cache is a performance feature and can be disabled without changing semantic output.

## 5. Revision and filesystem contract

- Resolve user refs to validated immutable Git object IDs before analysis. Use `merge-base(base_tip, head)` as the default PR comparison baseline, recording all three identities. `--exact-base` opts into direct base/head comparison.
- Multiple merge bases, missing/shallow history, unrelated histories, or missing objects produce an actionable incomplete/error result; do not guess. The offline kernel never fetches automatically.
- Read tree entries and blobs from Git objects, never import modules or execute files. Use a trusted absolute Git executable, option-safe ref resolution, validated OIDs, literal paths, disabled external helpers/replacement objects/lazy fetch and optional writes, an environment allowlist and closed inherited descriptors. Required Git behavior must be probed; missing support is explicit. No shell interpretation or repository hooks.
- Derive changed identity and required coverage from manifest/blob comparisons, independently of attributes. Generate admitted textual hunks with isolated per-blob comparisons at fixed trusted paths; repository attributes cannot suppress requested analysis. All commands share one deadline and streaming output bounds, including large documentation/data diffs.
- Use NUL-delimited tree/status metadata. Renames affect display and alignment, not file identity authority. Snapshot identity includes path, mode and blob identity. Decode source according to its encoding rules; do not silently replace undecodable bytes.
- Do not follow symlinks, initialize submodules, invoke filters, download large-file pointers, or expand archives. Record these exclusions. Binary files receive metadata-level review. Non-UTF-8 paths are explicitly unsupported in 0.1 and produce coverage diagnostics rather than disappearing.
- Dirty working-tree changes are excluded from E01 and noted in the report. E02's local-snapshot child package must materialize staged/unstaged content as immutable manifests, detect concurrent edits, and opt into untracked files explicitly. A mutable directory is not a snapshot.

## 6. Configuration and defaults

Trusted CI configuration comes from the base tip, with its blob digest recorded separately from the comparison merge base. Head changes are reviewed as proposed policy changes and cannot weaken their own review. Local configuration is an explicitly selected trusted input. Precedence: built-in defaults, trusted base TOML, explicit local overrides; CI refuses overrides that weaken required scope or thresholds.

Configuration is TOML, parsed through `tomllib`; unknown keys and invalid values are errors. Path filters are repository-relative glob patterns using a documented `fnmatchcase` contract, not platform-dependent shell expansion. Initially only `*`, `?`, and bracket classes are supported; `**` has no special recursive meaning. Paths always use `/` separators. Required source paths cannot be silently excluded by head content. Natural-language guidance is contextual data and cannot change executable permissions, provider destinations, rules, or blocking thresholds.

| Setting | E01 default / limit |
|---|---|
| profile | `structural`; `diff` must be explicit |
| runtime support | Python 3.12.x only in E01; parser patch version recorded exactly; other minor versions rejected until tested |
| runtime packages | zero third-party packages in deterministic kernel |
| files | at most 10,000 tracked entries per snapshot |
| blob bytes | at most 2,097,152 bytes per admitted text/source blob |
| total bytes | at most 134,217,728 admitted text/source bytes per snapshot |
| parse deadline | 2 seconds per blob, isolated child process |
| review deadline | 60 seconds total including 2 seconds reserved for bounded failure output |
| cache | private local storage only; CI defaults off; at most 268,435,456 bytes; no source text |
| record limits | depth 64; 100,000 aggregate worker/cache items, 1,000,000 report items; 4,194,304 UTF-8 bytes per string |
| protocol bytes | at most 8,388,608 bytes per worker message/cache entry/report |
| process output | at most 65,536 stderr bytes per process; 8,388,608 aggregate diff bytes |
| AI | disabled; no provider credentials needed |
| reviewed-code execution | disabled |
| default rule blocking | none; all three initial rules are advisory |
| publication | disabled in local review |

Limits are operator-changeable trusted policy. Exceeding one creates incomplete coverage, never successful silent truncation. A parser uses `-I -S`, a neutral working directory, trusted absolute paths and the same bounded process helper as Git. This does not restrict its filesystem authority. E01 supports trusted local operation; hostile CI requires a disposable credential-free isolated job with denied analysis egress and bounded filesystem/resource access. Arbitrary supplied Git metadata and externally restored caches are not admitted. Record actual enforcement and refuse the hostile profile where required controls are unavailable.

## 7. E01 language and rule contract

The `diff` profile provides exact changed-file/hunk facts and a deterministic walkthrough for text. It explicitly says semantic correctness and security were not evaluated.

The `structural` profile additionally analyzes changed and required related Python files within the implemented pattern scope. Requested structural analysis of other source languages is partial. Unsupported grammar, malformed input, decoding failure, process crash, timeout, or missing imported context remains visible. An empty findings list is not “clean code.” AST parsing alone is neither type checking nor whole-program analysis.

The coordinator builds expected entries from both manifests and trusted source classification, then expands required Python context through current supported static imports to a fixed point. Classify repository-resolved, pinned modeled-external and unresolved imports separately. Repository candidates/shadowing and ambiguities prevent unsupported external inference. Exact-runtime stdlib top-level identities do not prove availability or symbol semantics; only the narrow pinned subprocess symbol model supports PY003. Unknown imports become required unresolved-context entries; unrelated malformed files are not automatically required. File keys and lookup keys have separate discriminants; lookup identity includes the source occurrence, canonical target and relative level so distinct missing imports cannot collide. Workers may propose dependencies but cannot shrink scope. Seal the append-only scope before decisions and validate exactly one matching receipt per requested entry. Preserve excluded/unclassified inventory. Every gap identifies the capability, stable cause and a trusted recovery action. A valid head observation may survive unrelated incomplete coverage, while the whole review still returns exit 2.

Three advisory rules establish factual patterns and describe consequences under assumptions:

| ID | Exact initial condition | Claim boundary |
|---|---|---|
| PY001 | Mutable list/dict/set literal default plus a direct mutation of the unreassigned parameter in that function's own scope | Default object can persist across omitted-argument calls; intentional caching is possible |
| PY002 | Bare exception handler with a straight-line body and optional terminal return, without any raise | Captures exception categories including interruption; intentional supervision is possible |
| PY003 | A statically resolved `subprocess` invocation with literal `shell=True` | Requests shell-use review; does not claim injection or attacker input |

Resolve local binding shadowing and supported imports. Ambiguous resolution prevents the rule claim and records a diagnostic. PY001 handles direct subscript writes and these type-specific methods: list `append/extend/insert/pop/remove/clear/sort/reverse`, dict `update/setdefault/pop/popitem/clear`, set `add/update/remove/discard/pop/clear`. Constructor calls, unknown rebinding and alias-mediated writes are outside 0.1. PY002 excludes nested/branching handler control flow; conditional reraises are not silently called swallowing. PY003 handles only resolved `subprocess.run/Popen/call/check_call/check_output`, excluding shadowed aliases and unresolved dynamic attribute calls.

Imported module facts are used for supported symbol/context resolution only. There is no interprocedural taint, authorization proof, or framework model in E01. Report capability labels `generic_diff`, `python_structure`, `python_patterns`; later workers may advertise `calls`, `cfg`, `dataflow`, or `auth_obligations` independently.

## 8. Report and decision contract

Report schema version 1 includes the coordinator's `ReviewContract`, base tip/comparison base/head, runtime/rule/semantic-config digests, expected scope/reasons, examined receipts, exclusions, diagnostics, findings, evidence references and profile. Each finding has a rule/version, precise claim, side-aware source span, severity, advisory/blocking policy class, semantic anchor, witness digest, support/refutation state, delta classification and assumptions. Span records retain AST UTF-8 byte offsets and computed decoded-character columns separately; format renderers must not reread a mutable working tree to compute locations. Content-only parser facts and occurrence-bound facts are separate types; contextual resolution is run-local.

The report is a strict tagged union: `full` has the structure above, including honest partial coverage; `limit_failure` has known pinned identities, fixed cause/limit information, omitted-domain counts when known, exit 2 and explicit incomplete/details-omitted flags. It cannot carry findings, support or publication authority. The [security contract](../../security-architecture.md) specifies its 16-KiB/128-item bound and finalization reserve. Every format/consumer handles this variant, including SARIF run properties and incomplete execution status. Limits below the minimum envelope capacity are configuration errors. Renderers receive the same effective deadline and record limits explicitly; there is no new clock after analysis.

Delta classes are `newly_detected`, `persisting`, `no_longer_detected`, and `unknown`. A separate `evidence_delta` is `added`, `unchanged`, `changed`, or `unknown`. “Newly detected” becomes “introduced” only if comparable baseline analysis and reliable root-cause alignment support that causal statement. “No longer detected” never automatically becomes “fixed.” Existing sinks with changed/new paths need fresh review even if their obligation persists; publication eligibility must examine the evidence delta.

Findings retain all distinct obligations even when their locations overlap. Newline shifts do not duplicate an otherwise identical root cause. Ambiguous alignment yields unknown. Local sorting is deterministic by policy class, severity, path, side, line, rule and fingerprint. The full result remains available when UI comment limits apply.

Publication lifecycle uses a stable repository/PR/rule/obligation key separate from revision-bound observations and merge-base delta. A branch finding may be newly detected against the merge base on repeated pushes without needing another comment. Dismissal, publication state and substantive evidence are separate; changed witnesses merit renewed review. Ambiguous matching stays visible.

Evidence states are `undetermined`, `supported`, `refuted`, `conflicted`. Severity, evidence strength, coverage, and publication eligibility are separate. Initial supported evidence supports a pattern statement; it does not automatically support a defect statement.

Exit codes: `0` requested analysis complete with no configured blocking result, `1` complete with a configured blocker, `2` required analysis incomplete or unavailable, `3` tool/configuration/input failure. An optional advisory capability can be unavailable without failing an explicitly narrower requested profile, but the limitation must be in the report. Incomplete required analysis takes precedence over findings-based status. SARIF and Markdown reflect these semantics; consumers must not infer safety from the exit code or result count alone.

Canonical report data excludes timings, cache admission/miss/hit details, cache locations, invocation timestamps and publisher IDs; these appear in an `execution` section and do not affect semantic configuration identity. For completed logical analyses of the same inputs, canonical findings, scope, diagnostics and input manifests must match across clean and incremental runs. Wall-time exhaustion may make a cold run partial and a warm run complete; preserve each coverage receipt and do not claim equivalence until a complete clean comparison is available. Do not remove resource failures from the user-visible result to force equality.

All external records use a shared bounded strict decoder, including duplicate-key/nonfinite/type/range checks. Aggregate item accounting counts every object member and array element recursively. Terminal and Markdown rendering visibly escapes controls and directional text and prevents fence, HTML and link breakout. An owned builder percent-encodes each path segment under a fixed trusted repository origin and pinned commit; labels are escaped separately. Diagrams need opaque generated identifiers and a safe label serializer before activation. Machine-readable validity does not grant executable or publication authority.

## 9. Optional adapters

- **Language workers:** versioned JSON request/response over subprocess pipes; declared capabilities, pinned runtime/grammar, timeout and size caps. Per-language optional binding/grammar packages are allowed only outside the kernel. No automatic dependency installation.
- **AI:** one provider-neutral request interface, bounded context and output, no mandatory SDK, no autonomous browsing/tool execution. Later E03 defaults per review invocation or explicit chat answer: two requests, 65,536 serialized context bytes in aggregate, 2,048 requested output tokens per request, and 60 seconds aggregate including retries. Show used/remaining limits and require a deliberate trusted override for increases. Separate chat answers consume separate budgets; deployments also require an operator-set total spend cap. Bytes do not guarantee an input-token count. Provider prices, exact tokenization and retries require their own policy; display “cost unknown” when price data is absent. Preview transmitted paths and redact sensitive values; remote privacy cannot be guaranteed by a local filter. A valid source location proves only that the location exists; a behavioral claim remains a hypothesis until a matching deterministic or execution witness supports it.
- **CI context:** opt-in retrieval of exact-head run/job logs as bounded text with provider/run/commit provenance, size limits and redaction. Logs are untrusted context, cannot trigger command execution, and cannot substitute for a fresh validation run. Missing or stale logs remain explicit.
- **Scanner import:** a declared SARIF subset with producer/version/revision provenance. An imported claim preserves original trust; cross-tool agreement alone is not independent validation. Never execute tool names, links, commands or fixes embedded in a report.
- **Advisories:** opt-in lockfile lookup with endpoint allowlist, version/ecosystem matching, freshness receipt and no source upload. Installed version matching is distinct from exploitable code reachability.
- **Publisher:** validates bounded report schema and independently derived artifact/repository/PR/workflow/run association, current head and base tip, policy/scope/reviewer identities, locations and thresholds. Posts data, never executes artifacts. Same head in another PR cannot authorize replay. Rechecks immediately before publication and attaches reviewed identities; drift requires a new run. This is COMMENT feedback, not a transactionally current merge approval.
- **Runner:** separate E06 isolation design. Candidate tests and repository build scripts are untrusted executable code. Provider/publisher credentials never enter the runner. Patch validation targets the reviewed head tree, with old blob/mode preconditions for every changed path, an explicit allowed-path set, traversal/symlink escape rejection and stale-worktree refusal. Default proposals cannot edit workflow/policy files, executable bits, symlinks or submodules; exceptions require a distinct trusted action. A validation receipt pins patch digest, original/result tree, commands, runtime/image and test inputs. Renames/deletions need explicit support before acceptance.

## 10. CI and privacy design

Use a disposable unprivileged isolated analysis job and a narrowly privileged publisher. Ship a hardened template with full action commit pins, explicit minimal permissions and no persisted checkout credentials. Install/run a pinned trusted reviewer artifact outside head content. Pass PR strings as data, never interpolated shell fragments. Verify artifact provenance using platform run metadata, expected repository, PR, workflow, head and reviewed base policy/scope; checking attacker-supplied digests alone is insufficient. Publisher jobs never check out head or restore analysis-controlled caches. Bound JSON size/schema and render content as text. Untrusted forks receive report artifacts even when inline publication is unavailable.

Do not use a privileged target-branch workflow to execute head code. Keep publication credentials away from parsing, models and test runs. Publish only COMMENT feedback initially; no automatic approve or request-changes action. Missing permission or an API failure produces an explicit publication failure while retaining the local report.

Offline core egress is zero. Optional cache stores occurrence-free `ContentFacts`, not resolution, coverage, raw source or model prompts; facts may still reveal names and architecture. Private storage must enforce ownership, permissions and no-follow/reparse checks, or cache stays off. Schema-valid self-hashed foreign entries remain untrusted: omitted facts cannot be detected by checking emitted positives. Cache deletion is supported and disabling cache preserves completed semantic behavior. Logs redact credential values and avoid source dumps. Remote adapters need an operator-approved HTTPS origin/path, verified TLS, no ambient proxies/automatic redirects, credentials limited to that origin and a tested actual-address/egress policy; local providers use a distinct explicit profile. E03 must specify and test this transport and its retention limits.

## 11. Verification and implementation boundary

The [mathematical core](../../mathematical-core.md) defines the formal contracts. The [security and architecture contract](../../security-architecture.md) defines boundary controls and failure behavior. The [evaluation contract](../../evaluation.md) defines their test and empirical gates. The [E01 implementation plan](../plans/2026-10-03-review-kernel.md) maps the first stage to exact modules and meaningful adverse tests. The [master plan](../../../Master-Plan.md) now links scoped E02–E11 child specifications/plans, including completion plans for historical E03/E08 subsets. Its delivery expansion covers E07 packaged artifacts, E08 VS Code and neutral editor/assistant extension/plugin/MCP/skill surfaces, E09 Azure DevOps, E10 API/SDK/repository app and hosted/private deployments, and E11 enterprise operations. These delivery layers use the same coordinator-owned review contract and remain outside the deterministic kernel. Apply the [execution and acceptance gate](../../planning-contract.md) before any future implementation. No broad capability is implemented or accepted by describing it here.
