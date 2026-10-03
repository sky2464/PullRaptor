# PullRaptor Offline Review Kernel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task by task. Steps use checkbox syntax for tracking. Tasks 1–8 retain historical implementation checkboxes; Task 9's full acceptance audit is pending. Checkboxes alone are not acceptance evidence.

**Goal:** Deliver E01: a useful offline comparison of immutable revisions with honest coverage, three advisory Python patterns, stable evidence, and reproducible outputs.

**Architecture:** Read immutable Git blobs through one bounded subprocess helper. A trusted coordinator defines expected scope, extracts content-only facts in parser workers, binds occurrences, recomputes resolution/rules, validates receipts and aligns findings conservatively. Render safe canonical output; admit only a private optional parser cache.

**Tech stack:** Python standard library, Python 3.12.x as the only initially supported minor runtime, Git CLI, `unittest`. No third-party runtime/test packages. Packaging/build dependencies are outside this first plan.

**Spec:** [Product and architecture specification](../specs/2026-10-03-pullraptor-design.md), especially sections 5–8; [security and architecture contract](../../security-architecture.md); [mathematical contract](../../mathematical-core.md); [evaluation contract](../../evaluation.md).

## Global constraints

- Zero third-party packages in the deterministic kernel; Git executable required.
- AI disabled; reviewed-code execution disabled; no core network calls; publication disabled.
- At most 10,000 tracked entries, 2,097,152 bytes per admitted text/source blob, and 134,217,728 admitted text/source bytes per snapshot.
- Parse deadline 2 seconds per blob; review deadline 60 seconds including a 2-second failure-finalization reserve; cache cap 268,435,456 bytes.
- Protocol limits: depth 64, 100,000 aggregate worker/cache items, 1,000,000 report items, 4,194,304 UTF-8 bytes per string, 8,388,608 bytes per worker message/cache entry/report, 65,536 stderr bytes per process and 8,388,608 aggregate textual diff bytes. Count each object member/array element recursively; bound strings and keys. Reserve a 16,384-byte/128-item failure variant.
- Local repository/host/cache writer are trusted; hostile CI needs E02's separate disposable credential-free isolation profile. No arbitrary supplied Git metadata or restored/shared cache admission.
- All initial rules advisory; no default blockers.
- Default profile `structural`; explicit `diff` profile does not evaluate semantic correctness/security.
- Exit 0 complete/nonblocking, 1 complete/configured blocker, 2 required analysis incomplete, 3 tool/config/input failure.
- Keep competing product names and domains out of project files, dependencies, fixtures, and copy.
- Proposed production target: at most 3,000 nonblank, noncomment lines and 15 modules; readability and validation take priority.

## Review focus

1. A PR that changes its own policy must not weaken that run: Task 2 pins base-tip configuration.
2. An unresolved import that becomes resolvable must not retain stale results: Tasks 4 and 7 rebuild resolution and compare clean output.
3. A finding moved by a rename or Unicode edit must not become a false new defect: Tasks 3 and 6 validate side-aware spans and alignment.
4. A parser timeout, unsupported source language or baseline failure must not look like a clean review: Tasks 4 and 8 pin coverage/exit behavior.
5. Hostile Git configuration and untrusted source must not execute: Tasks 3, 4 and 8 test the process boundary and zero egress.
6. A worker that omits a required file cannot declare success: Tasks 1, 6 and 7 compare receipts against coordinator-owned scope.
7. Schema-valid cache entries with missing facts are not authenticated: Task 7 rejects foreign/shared storage instead of trusting a checksum.
8. Malformed records and attacker-controlled display text cannot exhaust or take over output: Tasks 1, 3 and 8 cover bounded decoding, pipes and rendering.

## File and interface map

Create `src/pullraptor/` with `__init__.py`, `__main__.py`, `models.py`, `config.py`, `process.py`, `git_snapshot.py`, `diff.py`, `python_facts.py`, `parser_worker.py`, `rules.py`, `evidence.py`, `kernel.py`, `cache.py`, and `render.py`. This is 14 proposed production modules, within the 15-module target. Run the trusted worker entry script with the trusted interpreter's absolute path and `-I -S`; bootstrap only pinned sibling kernel modules from absolute trusted installation paths. Never add the repository or ambient `PYTHONPATH` to its import search. The shared strict codec remains in `models.py`, not duplicated in each worker.

Create a stdlib `tests/` package with `helpers.py` and one test module per task, plus a versioned fixture corpus. Tests exercise user outcomes and contract failure modes, not line-for-line implementation copies.

### Task 1: Immutable records, bounded codec and canonical output

**Files:** `src/pullraptor/__init__.py`, `src/pullraptor/models.py`, `tests/__init__.py`, `tests/test_models.py`.

**Produces:** frozen records `Limits`, `RecordLimits`, `Deadline`, `ProcessBounds`, `ProcessResult`, `Config`, `BlobRef`, `Snapshot`, `Span`, `Change`, `ContentFacts`, `BoundFacts`, `ResolvedFacts`, `FactResult`, `Diagnostic`, `ScopeEntry`, `ReviewContract`, `CoverageReceipt`, `Evidence`, `Finding`, `FullReport`, `LimitFailure`; `Report = FullReport | LimitFailure` is a tagged union. Export `decode_record(payload: bytes, schema: str, limits: RecordLimits) -> dict[str, object]` and `canonical_bytes(report: Report, *, limits: RecordLimits, deadline: Deadline) -> bytes`. Export a small `LimitExceeded` exception carrying only trusted cause/limit/count fields. Keep records flat and add no generic framework. Deadline stores absolute work/final cutoffs derived from the same invocation start; it is operational, never canonical data.

Required fields: Snapshot has `oid`, sorted BlobRef(path/path_bytes/mode/blob_oid/size) entries and diagnostics; path is absent when bytes cannot decode. JSON manifests encode path bytes as hex. Span has path/side, 1-based lines, 0-based UTF-8 byte offsets with exclusive end, and separate 1-based decoded-character columns. ContentFacts has blob digest, exact runtime/schema/extractor identities, relative locations, symbols, imports, pattern facts and unsupported constructs, with no occurrence path/side. BoundFacts adds validated snapshot/path/side; ResolvedFacts adds current run-local resolution. FactResult has ContentFacts or relative failure diagnostics, bound by the coordinator later. Finding includes rule/version/obligation/anchor/span/claim/severity/state/witness/assumptions/delta/evidence_delta. ReviewContract pins base tip/comparison base/head, semantic policy/config/tool identities, profile, expected scope/reasons and coordinator-owned discovery completion. File scope keys contain kind/snapshot/path-bytes/capability; import-lookup keys contain kind/snapshot/source occurrence/canonical target/relative level/capability, not invented paths. CoverageReceipt references the key/contract identity and status/cause. FullReport keeps the contract, receipts, inventory/exclusions, findings, diagnostics and separate execution metadata. Config separates semantic settings from cache controls. Evidence stores claim key/type/context, support/refute flags, witnesses and assumptions.

Schema 1 requires a `kind` tag. `full` uses FullReport above. `limit_failure` uses fixed fields: `schema`, `kind`, `known_inputs` (base tip/comparison base/head/policy/reviewer digest, each string or null), `exit_code=2`, `analysis_complete=false`, `details_omitted=true`, a fixed cause enum, `limit` (name/cap/observed lower bound or null), and `omitted_domains` (fixed domain enum/count or null). No arbitrary text/path, findings, support or publication fields are accepted. Bound the entire variant to 16,384 bytes/128 collection items, including renderer wrappers. Normal full serialization obeys the work cutoff; only fixed failure rendering uses the final reserve. LimitFailure has no whole-scope negative claim and is never inline-publishable.

- [x] Write `test_canonical_excludes_execution_metadata`: duration/cache admission/hit/location changes leave canonical bytes identical; coverage/witness changes do not. Add `test_invalid_span_rejected`, `test_content_facts_cannot_carry_occurrence`, `test_duplicate_keys_rejected`, `test_nonfinite_json_rejected`, `test_bool_not_integer`, and byte/depth/item/string/surrogate boundary cases.
- [x] Add `test_report_union_strict_tags`, `test_item_accounting_recursive`, `test_limit_failure_cannot_claim_support_or_complete` and `test_two_missing_imports_have_distinct_keys`. Round-trip both variants and prohibit unknown authority fields.
- [x] Run `PYTHONPATH=src python3.12 -m unittest tests.test_models -v`; verify meaningful failure before implementing records.
- [x] Implement a string-aware bounded nesting precheck, strict UTF-8/duplicate-key/nonfinite decoding and schema/type/range/count/string validation. Canonical encoding uses sorted keys, stable list order and `allow_nan=False`. Bound diagnostics too. Invalid worker data is partial; invalid cache is a miss; invalid publication input is rejected. Keep arbitrary source bytes out of report JSON.
- [x] Run the same command; require all assertions pass. Record parser/runtime version without assuming Git object ID length is 40.
- [x] Commit the task after verification in the existing Git checkout; preserve unrelated work and do not fabricate commit evidence.

### Task 2: Trusted declarative policy

**Files:** `src/pullraptor/config.py`, `tests/test_config.py`, `tests/helpers.py`.

**Consumes:** Config/Limits from Task 1.

**Produces:** `load_config(policy_bytes: bytes | None, overrides: dict[str, object], *, ci: bool) -> Config`; `matches_path(path: str, patterns: tuple[str, ...]) -> bool`. Caller supplies base-tip bytes in CI. Helpers provide `make_repo(files: dict[str, bytes]) -> FixtureRepo` with `commit(changes: dict[str, bytes | None]) -> str` and read-only commit IDs.

- [x] Write `test_defaults_exact` asserting the limits/profile above; `test_unknown_key_error`; `test_glob_semantics` asserting `*` follows `fnmatchcase`, `**` has no special meaning, and separators normalize to `/`; `test_ci_override_cannot_weaken_required_scope`.
- [x] Add `test_minimum_finalization_capacity`: duration below 3 seconds, report bytes below 16,384, item capacity below 128, report depth below 8 or per-string capacity below 256 bytes is a configuration error. Reserve remains part of total duration, not a timeout extension.
- [x] Run `PYTHONPATH=src python3.12 -m unittest tests.test_config -v`; verify failure.
- [x] Implement TOML parsing/validation and explicit precedence. Default source suffix inventory is `.py,.pyi,.js,.jsx,.ts,.tsx,.go,.rs,.java,.cs,.c,.h,.cpp,.hpp,.cc,.php,.rb,.swift,.kt,.kts,.scala,.sh,.sql`; every file still receives generic inventory. Do not import or evaluate configuration code. Policy changes in head are displayed as changes only.
- [x] Run tests; require invalid/weakening configuration to fail with exit-class 3 rather than silently fall back.
- [x] Commit verified policy behavior.

### Task 3: Safe immutable snapshots and exact diff facts

**Files:** `src/pullraptor/process.py`, `src/pullraptor/git_snapshot.py`, `src/pullraptor/diff.py`, `tests/test_process.py`, `tests/test_snapshot.py`, `tests/test_diff.py`.

**Consumes:** Limits, Deadline, ProcessBounds, Snapshot, Change and Diagnostic.

**Produces:** `run_bounded(argv: tuple[str, ...], *, cwd: Path, env: dict[str, str], deadline: Deadline, bounds: ProcessBounds) -> ProcessResult`; `resolve_inputs(repo: Path, base_ref: str, head_ref: str, limits: Limits, deadline: Deadline, *, exact_base: bool) -> tuple[str, str, str]`; `read_snapshot(repo: Path, oid: str, limits: Limits, deadline: Deadline) -> Snapshot`; `read_blob(repo: Path, blob_oid: str, limits: Limits, deadline: Deadline) -> bytes`; `changes(repo: Path, base: Snapshot, head: Snapshot, limits: Limits, deadline: Deadline) -> tuple[Change, ...]`. Resolve returns base tip/comparison base/head. Only trusted boundary callers construct argv/environment; source data cannot choose executables/options. Limits and the shared absolute deadline are mandatory for every operation.

- [x] Write `test_merge_base_not_base_tip`, `test_refs_pinned_before_read`, `test_dirty_tree_ignored`, `test_shallow_missing_object_incomplete`, `test_multiple_merge_bases_rejected` and `test_replace_objects_ignored`.
- [x] Write `test_nul_metadata_paths` for spaces/tab/newline; `test_non_utf8_path_reported`; `test_symlink_and_submodule_not_followed`; `test_binary_and_deleted_file_preserved`; `test_hostile_external_diff_textconv_fsmonitor_not_executed`. The hostile test config points to a sentinel-writing script; sentinel must remain absent.
- [x] Add `test_option_like_ref_rejected`, `test_promisor_object_never_lazy_fetches`, `test_attributes_cannot_hide_source`, `test_ambient_git_config_ignored`, `test_worker_environment_has_no_credentials`, `test_inherited_handles_closed`, `test_output_flood_stopped`, `test_large_text_diff_bounded`, `test_shared_deadline_not_reset` and timeout process-tree cleanup. Exercise required Git flag/version admission and unsupported OS enforcement diagnostics.
- [x] Run `PYTHONPATH=src python3.12 -m unittest tests.test_process tests.test_snapshot tests.test_diff -v`; verify failure.
- [x] Implement streaming bounded stdout/stderr, trusted absolute executables, minimal environment, closed handles and kill/reap on overflow/deadline. Never buffer unlimited `communicate()` output. Probe required Git behavior; validate refs with `--verify --end-of-options` then use OIDs only. Disable lazy fetch, replacement objects, optional writes, attributes/helpers and ambient config effects. Do not widen global repository trust. Enforce tree/text/blob limits; Task 7 enforces aggregate admitted bytes. Derive changed identity from manifests, then use isolated fixed-path per-blob text comparisons with no repository attributes; diff exit 1 is normal. Preserve original path bytes separately from display encoding diagnostics.
- [x] Run all three modules; require exact side-aware hunks, bounded metadata/diff output, explicit over-limit diagnostics and no execution or fetch. Record actual OS process/resource controls; local mode cannot claim filesystem isolation.
- [x] Commit verified ingestion behavior.

### Task 4: Bounded Python facts and explicit capabilities

**Files:** `src/pullraptor/python_facts.py`, `src/pullraptor/parser_worker.py`, `tests/test_python_facts.py`, `tests/fixtures/python/`.

**Consumes:** Blob bytes, current manifest occurrence, Limits and the shared Deadline.

**Produces:** `extract_python(source: bytes, limits: Limits, deadline: Deadline) -> FactResult`; `bind_facts(content: ContentFacts, source: bytes, snapshot: Snapshot, path: str, side: str) -> BoundFacts`; `resolve_context(facts: tuple[BoundFacts, ...], manifest: Snapshot) -> tuple[tuple[ResolvedFacts, ...], tuple[Diagnostic, ...]]`. Validate blob identity and source spans when binding. Resolution is recomputed each run. Worker protocol uses one strict bounded JSON request/response with base64 source and exact protocol identity; no network/tools. The parser deadline is the minimum of the shared deadline and its per-blob allowance.

- [x] Write `test_unicode_columns_crlf_exact`, `test_scope_shadowing_and_aliases`, `test_nested_functions_not_outer_mutation`, `test_parameter_reassignment`, `test_missing_import_diagnostic`, `test_new_module_resolves_previous_miss`, and `test_parse_failure_preserves_diff_coverage`.
- [x] Write `test_timeout_or_worker_crash_partial`, `test_import_side_effect_not_executed`, and `test_oversized_source_not_sent_to_worker`. Use a trusted test worker that stalls/crashes to test deadline behavior; do not rely on flaky timing of a huge real AST.
- [x] Add `test_isolated_startup_ignores_site_and_paths`, `test_neutral_worker_cwd`, `test_wrong_blob_or_span_rejected`, `test_worker_duplicate_fields_partial` and `test_maximum_source_base64_fits_protocol`. Test missing, cyclic, ambiguous and newly resolvable static import closure without importing source.
- [x] Add `test_stdlib_identity_not_missing_context`, `test_subprocess_alias_modeled`, `test_local_subprocess_shadows_external_model`, `test_ambiguous_module_no_external_fallback`, `test_missing_external_module_partial` and `test_resolving_x_leaves_y_missing`. Pin the exact interpreter's `sys.stdlib_module_names` digest and the narrow subprocess symbol model; stdlib classification alone does not establish callable semantics or availability. Supported repository candidates take precedence; unresolved dynamic imports stay explicit boundaries. No installed external package discovery/execution.
- [x] Run `PYTHONPATH=src python3.12 -m unittest tests.test_python_facts -v`; verify failure.
- [x] Implement stdlib parsing through the shared process helper using `-I -S`, trusted sibling-module loading, neutral cwd and minimal environment. Extract only content facts with encoding detection, lexical bindings, relative spans and unsupported constructs. Coordinator binding adds path/side/snapshot. Parse required import closure and conservatively re-resolve against the current full manifest. No symbol inference from string similarity, runtime imports or CFG/taint claims.
- [x] Run tests; exact diagnostic shape is `PullRaptor: PY_PARSE_FAILED path:line: Python <runtime-major.minor> could not parse this file; semantic review skipped.` Parsing and scope coverage remain separate fields. AST version differences are recorded and tested on every runtime claimed supported.
- [x] Commit verified facts and worker boundary.

### Task 5: Small advisory rule pack

**Files:** `src/pullraptor/rules.py`, `tests/test_rules.py`, `tests/fixtures/rules/`.

**Consumes:** fully current ResolvedFacts, trusted Config and Snapshot identity.

**Produces:** `evaluate_rules(facts: tuple[ResolvedFacts, ...], snapshot: Snapshot, config: Config) -> tuple[Finding, ...]`. Initial findings have no delta until Task 6.

- [x] Write at least 10 positive and 10 negative/ambiguous fixtures per rule with expected claim/evidence/blocking status. Pin `test_intentional_patterns_never_defect_claim`, `test_shadowed_subprocess_no_shell_claim`, `test_conditional_reraise_not_classified_as_swallowed`, and `test_untrusted_command_not_inferred_from_shell_true`.
- [x] Run `PYTHONPATH=src python3.12 -m unittest tests.test_rules -v`; verify failure.
- [x] Implement PY001 for list/dict/set literals, direct subscript writes, and unreassigned parameter calls to list `append/extend/insert/pop/remove/clear/sort/reverse`, dict `update/setdefault/pop/popitem/clear`, or set `add/update/remove/discard/pop/clear`. Recognize these only for the known literal type. Exclude alias-mediated writes and nested scopes. Unknown prior rebinding stops the claim.
- [x] Implement PY002 only for a bare handler whose body is straight-line operations with optional terminal `return` and no `raise`; nested/branching control flow is unclassified. Implement PY003 only for resolved `subprocess.run/Popen/call/check_call/check_output` with literal true shell keyword. Attach exact witnesses, stated consequences, rule version and advisory class. Never recommend replacing a mutable default without considering the intended API semantics.
- [x] Run fixtures; all initial findings must be advisory and satisfy their exact factual predicates. No shell pattern may contain an injection/exploit assertion.
- [x] Commit verified rules.

### Task 6: Evidence, alignment and policy decisions

**Files:** `src/pullraptor/evidence.py`, `tests/test_evidence.py`.

**Consumes:** both snapshot rule outputs, trusted sealed ReviewContract and independently keyed receipts/config/version records.

**Produces:** `accumulate(evidence: tuple[Evidence, ...]) -> tuple[bool, bool]`; `align_findings(base: tuple[Finding, ...], head: tuple[Finding, ...], *, comparable: bool) -> tuple[Finding, ...]`; `validate_receipts(contract: ReviewContract, receipts: tuple[CoverageReceipt, ...]) -> tuple[Diagnostic, ...]`; `decide(contract: ReviewContract, receipts: tuple[CoverageReceipt, ...], findings: tuple[Finding, ...], diagnostics: tuple[Diagnostic, ...], config: Config) -> int`.

- [x] Write `test_all_evidence_accumulations` over all 16 pair combinations; `test_different_claim_or_revision_cannot_accumulate`; `test_conflict_not_blocker`; `test_shifted_line_same_obligation`; `test_ambiguous_rename_unknown`; `test_base_parse_failure_delta_unknown`; `test_old_sink_new_witness_retained`; `test_incomplete_precedes_finding_exit`; `test_fatal_diagnostic_exit3`.
- [x] Add `test_missing_receipt_cannot_complete`, `test_duplicate_or_foreign_receipt_rejected`, `test_wrong_revision_or_capability_rejected`, `test_worker_cannot_shrink_scope` and `test_valid_head_claim_survives_unrelated_partial`. Test stable incomplete causes and trusted recovery guidance, including unsupported language, unresolved import and exhausted budget.
- [x] Run `PYTHONPATH=src python3.12 -m unittest tests.test_evidence -v`; verify failure.
- [x] Implement componentwise accumulation only within one claim/snapshot/model context, conservative root-cause matching and separate policy evaluation. Match only unique rule/version + qualified symbol + normalized obligation in one module; omit position attributes from semantic AST keys. Cross-path matching requires a unique exact-blob rename; modified/multiple candidate renames remain unknown. Compare semantic witness separately from fresh revision binding; retain new paths/obligations. Validate coordinator discovery completion, expected-scope/receipt bijection and identities before decisions; do not accept worker-reported scope as authority. Keep local valid observations during unrelated partial work, but require complete applicable analysis for negative whole-scope claims. Never infer introduced/fixed from subtraction. Pattern evidence cannot satisfy defect-blocking policy. Fatal tool/config/input failure returns 3; otherwise incomplete discovery/required receipts return 2 before blocker evaluation. LimitFailure bypasses finding evaluation and always returns 2.
- [x] Run tests; assert canonical ordering and states. Initial default decision is 0 only when required coverage completes; otherwise 2/3 as specified.
- [x] Commit verified evidence behavior.

### Task 7: Disposable parse cache and orchestration

**Files:** `src/pullraptor/cache.py`, `src/pullraptor/kernel.py`, `tests/test_cache.py`, `tests/test_kernel.py`.

**Consumes:** previous task interfaces.

**Produces:** `cache_key(blob_digest: str, runtime: str, schema_version: str, extractor_digest: str) -> str`; `load_facts(cache_dir: Path, key: str, limits: Limits) -> ContentFacts | None`; `store_facts(cache_dir: Path, key: str, facts: ContentFacts, limits: Limits) -> None`; `review(repo: Path, base_ref: str, head_ref: str, overrides: dict[str, object] | None = None, *, started_at: float | None = None, ci: bool = False, exact_base: bool = False, use_cache: bool = True) -> tuple[Report, Deadline, RecordLimits]`. CLI supplies its once-recorded monotonic start. The coordinator returns effective operational controls explicitly for rendering, separately from Report. Internal helpers build/expand/seal ReviewContract. Initial ref/policy preparation must finish within one second of invocation start, with final cutoff at start+3 seconds; otherwise return LimitFailure under those bootstrap controls. After trusted validation, configured duration recomputes cutoffs from the original start. Never reset the clock or permit a slower bootstrap to outrun a subsequently discovered minimum duration. Analysis/full serialization use the work cutoff; fixed failure output uses the reserved final cutoff.

Cached ContentFacts have no path/side; Task 4 binds current occurrences. If extraction later uses semantic configuration, extend its key before reuse. Rules/resolution are always rerun. Resolve refs once, load base-tip policy, build expected roots from both manifests, expand classified static imports append-only, seal scope and validate receipts. Unknown lookup context becomes a distinct required entry; discovery exhaustion leaves coordinator discovery completion false and forces partial status even if all known receipts completed. Never accept policy or expected scope of unknown origin. The extractor digest covers every fact-producing/binding-normalization component, including trusted worker dependencies, not only one script. CI disables cache regardless of the local default. Cache operations, miss reasons and paths stay outside semantic configuration/canonical data.

- [x] Write `test_clean_warm_corrupt_cache_identical`, `test_atomic_interrupted_write_miss`, `test_runtime_schema_change_miss`, `test_same_blob_different_paths_rebound`, `test_size_cap`, and `test_full_manifest_resolution_recomputed`.
- [x] Add `test_schema_valid_foreign_cache_ignored`, `test_shared_permissions_cache_disabled`, `test_cache_symlink_or_reparse_refused`, `test_ci_cache_off`, `test_all_extractor_components_invalidate`, `test_scope_import_closure_fixed_point`, `test_unrelated_malformed_file_not_required`, `test_unresolved_context_required` and `test_incomplete_discovery_cannot_seal_complete_scope`.
- [x] Add mutation sequences: rename, delete a dependency, add a previously missing module, alter policy, move a witness, exceed a limit and recover. For every completed analysis assert full canonical equality between cache-enabled and no-cache runs. Separately inject cold deadline exhaustion and warm completion, assert visible partial/complete receipts, then compare after a complete clean replay.
- [x] Add `test_slow_preparation_short_policy_still_bounded`: policy preparation that would take five seconds is stopped at the one-second bootstrap work cutoff and yields valid failure output by its three-second final cutoff; a successfully read three-second policy preserves the original cutoffs.
- [x] Run `PYTHONPATH=src python3.12 -m unittest tests.test_cache tests.test_kernel -v`; verify failure.
- [x] Implement private owner/permission-checked descriptor-relative no-follow cache access and atomic bounded writes outside reviewed trees. Require equivalent verified controls on other OSes or disable cache. Foreign/shared/restored entries are misses even with valid checksums; checking emitted positives does not detect omissions. Private host/writer trust is an explicit assumption. Implement the coordinator pipeline, aggregate text/source bounds, exact scope reasons, relative-fact binding, fresh resolution and independent receipts. Retain unfinished/discovery gaps; rebuild both revision outputs before alignment. Resolve configuration from base tip, not head or merge base.
- [x] Run both modules; validate no raw source/model data in cache, no execution metadata in canonical comparison, and no stale lookup reuse.
- [x] Commit verified orchestration.

### Task 8: CLI, formats and user-path acceptance

**Files:** `src/pullraptor/__main__.py`, `src/pullraptor/render.py`, `tests/test_cli.py`, `tests/test_render.py`, `tests/fixtures/e2e/`; update `README.md` with actually supported usage only.

**Consumes:** review/decide and Report.

**Produces:** `render_markdown(report: Report, *, limits: RecordLimits, deadline: Deadline) -> str`; `render_json(report: Report, *, limits: RecordLimits, deadline: Deadline) -> str`; `render_sarif(report: Report, *, limits: RecordLimits, deadline: Deadline) -> str`; `main(argv: list[str] | None = None) -> int`. Renderers use the returned operational controls, never hidden state or a fresh clock. Full serialization raises the typed LimitExceeded on size/item/work-cutoff exhaustion; CLI constructs Task 1's fixed LimitFailure, renders it using the reserve and returns 2. Renderers do not silently convert a report while returning only text; caller status stays explicit.

- [x] Write `test_structural_python_complete`, `test_structural_other_language_partial_exit2`, `test_explicit_diff_profile_scope_statement`, `test_config_error_exit3`, `test_empty_findings_not_safety_claim`, `test_deleted_line_sarif_side`, `test_unicode_sarif_character_columns`, and `test_stdout_machine_format_stderr_diagnostics`.
- [x] Add `test_terminal_escape_controls_and_bidi`, `test_markdown_fence_html_link_breakout`, `test_links_only_from_trusted_identity`, `test_uri_reserved_segments_roundtrip`, `test_report_byte_limit_never_complete`, `test_requested_and_examined_scope_visible` and `test_recovery_guidance_not_attacker_commands`. Use one owned fixed-origin URI builder with percent-encoded path segments and independently escaped labels. Bound record construction/serialization and use the strict LimitFailure variant; never shorten a complete report silently.
- [x] Test byte/item exhaustion below manifest-entry limits and analysis exhaustion just before expensive serialization in all three formats. Validate failure JSON, SARIF run properties/`executionSuccessful=false` and Markdown omissions within the fixed reserve/cap; no clock reset, no supported or clean claim, exit 2. Test output backpressure/closed pipes and record actual supported-OS output/deadline enforcement.
- [x] Add `test_core_network_disabled` by denying sockets/DNS during an end-to-end run, and rerun sentinel Git/source-execution cases through the CLI. Every report includes comparison identities and coverage.
- [x] Run `PYTHONPATH=src python3.12 -m unittest tests.test_cli tests.test_render -v`; verify failure.
- [x] Implement `review --base --head --exact-base --profile structural|diff --format markdown|json|sarif --no-cache`, concise walkthrough, expected/examined scope, stable gap causes/trusted recovery actions and safe side-aware rendering. Reject unsupported Python minor runtimes. Visibly escape terminal controls/directional text and Markdown fences/HTML/links; source data cannot supply active URLs or commands. Task 4's decoded-character columns feed SARIF without rereading the tree. Only current-head alerts enter SARIF `results`; baseline-only results remain history properties with baseline identity. Include partial status in every format and obey the shared remaining deadline/output limits.
- [x] Run `PYTHONPATH=src python3.12 -m unittest discover -s tests -v`. Manually run the three documented commands on pinned positive/negative/mixed-language fixture repositories. Save exact outputs and exit codes.
- [x] Measure cold/warm time and RSS against the documented fixture; report actual values even if targets fail. Audit imports, subprocesses, file/module count and runtime requirements. Verify competitor-name/domain absence and all local documentation links.
- [x] Perform whole-kernel review of trust boundaries, adverse inputs and scope claims. Record limitations, update E01 status only with acceptance evidence, and commit verified deliverable. Do not begin E02–E06 without their child plans.

### Task 9: Audit and independently accept the implemented E01 scope

**Status:** Unexecuted acceptance work. Do not rerun or credit Tasks 1–8 from checkbox state alone. Apply the [execution contract](../../planning-contract.md).

**Files:** Produce `docs/acceptance/E01.md` and `docs/acceptance/artifacts/E01/`; add missing adverse fixtures only in the affected existing test modules. A discovered production defect needs a scoped correction task before implementation.

**Consumes:** Current reviewed E01 source/artifact revision, Tasks 1–8 contracts, parent specification §§5–8, and the evaluation contract.

**Produces:** A revision-bound acceptance record with per-criterion `passed`, `failed`, `not_run` or `stale` states and an independent acceptance decision. No new kernel interface.

| ID | Required acceptance |
|---|---|
| E01-A1 | Map every Task 1–8 required behavior/adverse case to an actual test/fixture and saved result; zero egress/source execution, exact locations, scope honesty, bounded process/record/output behavior and all four evidence states must pass. Missing named tests remain gaps, never credited by a similarly named suite. |
| E01-A2 | Completed clean/warm/corrupt/absent-cache mutation runs agree on full canonical data; separately record partial cold runs and successful full replay. Each PY001–PY003 rule has at least 10 positive and 10 counterexample/ambiguous cases with exact advisory claim boundaries. |
| E01-A3 | Record code/module/runtime/dependency/size inventory and at least 30 cold/warm benchmark repetitions on the master-plan's pinned 2-vCPU/4-GiB, 10,000-file fixture; report p95/RSS and actual enforcement. Independently accept the local review/summary/exact-line/coverage-recovery flow and all limitations. |

- [x] **Step 1:** Inventory actual tests against each requirement in Tasks 1–8 and E01-A1–A3; record missing cases before running anything. Define fixture IDs and expected outcomes. Assertions include `canonical_clean == canonical_warm == canonical_corrupt` for completed runs, `partial_exit == 2`, and all initial findings `policy_class == "advisory"`. Evidence: `docs/acceptance/artifacts/E01/test_inventory.json` (2026-10-03).
- [x] **Step 2:** In an authorized trusted development environment, run `PYTHONPATH=src python3.12 -m unittest discover -s tests -v`; save command/runtime/revision/exit/output. Test execution here does not admit arbitrary reviewed-code execution in analysis. Add focused adverse fixtures where inventory identifies a gap and confirm they meaningfully fail before any scoped correction. Evidence: `docs/acceptance/artifacts/E01/unittest_discover_verbose.log`, exit code 0; no new adverse gaps identified.
- [ ] **Step 3:** Run the pinned mutation/corpus/user-flow fixtures and 30-repetition benchmark; save full reports and raw timing/RSS data. Compare byte-for-byte completed canonical reports, not finding counts. Missing fixtures or unrun benchmarks stay `not_run`. Mutation/corpus tests pass in CI; master-plan 10k-file / 30-rep benchmark and RSS remain `not_run` (`artifacts/E01/micro_benchmark.json` is non-authoritative).
- [x] **Step 4:** Complete `docs/acceptance/E01.md` with every criterion, actual resource results and unresolved limitations; obtain independent acceptance review. Keep E01 acceptance pending on any failed/not_run/stale required criterion. Do not infer held-out accuracy or enable blockers from pattern fixtures. Record written; independent decision **pending**.
- [ ] **Step 5:** Commit the reviewed record on an allowed branch. Only an accepted record promotes E01 in the master plan; the E01/E02 usefulness pilot additionally gates wider delivery/breadth.

## Handoff

E01 production modules and historical tests exist; full acceptance awaits Task 9. E02/E03/E07/E08 contain partial implementations of their parent scope. E04–E06 and E09–E11 remain proposed. The master plan links scoped child documents for all packages; subsequent execution needs authorization, accepted prerequisites and fresh acceptance evidence.
