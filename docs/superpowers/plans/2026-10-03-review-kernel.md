# PullRaptor Offline Review Kernel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task by task. Steps use checkbox syntax for tracking. This is a proposed plan; no task has been executed.

**Goal:** Deliver E01: a useful offline comparison of immutable revisions with honest coverage, three advisory Python patterns, stable evidence, and reproducible outputs.

**Architecture:** Read immutable Git blobs through a fixed subprocess boundary. Extract compact Python facts in an isolated parser worker, recompute resolution and rules for both revisions, align findings conservatively, and render a canonical report. Cache parsing facts only.

**Tech stack:** Python standard library, Python 3.12.x as the only initially supported minor runtime, Git CLI, `unittest`. No third-party runtime/test packages. Packaging/build dependencies are outside this first plan.

**Spec:** [Product and architecture specification](../specs/2026-10-03-pullraptor-design.md), especially sections 5–8; [mathematical contract](../../mathematical-core.md); [evaluation contract](../../evaluation.md).

## Global constraints

- Zero third-party packages in the deterministic kernel; Git executable required.
- AI disabled; reviewed-code execution disabled; no core network calls; publication disabled.
- At most 10,000 tracked entries, 2,097,152 bytes per source blob, and 134,217,728 source bytes per snapshot.
- Parse deadline 2 seconds per blob; review deadline 60 seconds; cache cap 268,435,456 bytes.
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

## File and interface map

Create `src/pullraptor/` with `__init__.py`, `__main__.py`, `models.py`, `config.py`, `git_snapshot.py`, `diff.py`, `python_facts.py`, `parser_worker.py`, `rules.py`, `evidence.py`, `kernel.py`, `cache.py`, and `render.py`. This is 13 proposed production modules. `parser_worker.py` is a standalone stdlib script so `python -I path/to/parser_worker.py` works without relying on `PYTHONPATH` or importing reviewed code.

Create a stdlib `tests/` package with `helpers.py` and one test module per task, plus a versioned fixture corpus. Tests exercise user outcomes and contract failure modes, not line-for-line implementation copies.

### Task 1: Immutable records and canonical output

**Files:** `src/pullraptor/__init__.py`, `src/pullraptor/models.py`, `tests/__init__.py`, `tests/test_models.py`.

**Produces:** frozen records `Limits`, `Config`, `BlobRef`, `Snapshot`, `Span`, `Change`, `PythonFacts`, `FactResult`, `Diagnostic`, `Coverage`, `Evidence`, `Finding`, `Report` and their strict JSON conversions. Export `canonical_bytes(report: Report) -> bytes`.

Required fields: Snapshot has `oid`, sorted `entries` of BlobRef(path/path_bytes/mode/blob_oid/size) and ingestion diagnostics; path is absent when bytes cannot decode. JSON manifests encode path bytes as hex, not lossy replacement text. Span has path, left/right side, 1-based start/end lines, 0-based UTF-8 byte offsets with an exclusive end, and separately computed 1-based decoded-character start/end columns. PythonFacts has path, blob digest, runtime/schema version, symbols, imports, pattern facts and unsupported constructs; FactResult has facts or failure diagnostics. Finding includes rule/version/obligation/anchor/span/claim/severity/state/witness/assumptions/delta/evidence_delta. Report includes input manifest, profile, findings, coverage, diagnostics and a separate execution section. Config contains profile, limits, excludes, source suffixes, trusted-policy digest and cache controls. Coverage enumerates every requested file/capability with complete/partial/not-evaluated status. Evidence stores claim key/type, snapshot/model context, support/refute flags, witness references and assumptions. Add fields only when later tasks actually consume them.

- [ ] Write `test_canonical_excludes_execution_metadata`: two reports differing only in duration/cache-hit/invocation-time fields have identical bytes; changing coverage or a witness changes bytes. Add `test_invalid_span_rejected` and `test_nonfinite_json_rejected`.
- [ ] Run `PYTHONPATH=src python3.12 -m unittest tests.test_models -v`; verify meaningful failure before implementing records.
- [ ] Implement records and canonical JSON with sorted keys, stable list ordering and `allow_nan=False`. Reject missing/unknown fields in external records. Keep arbitrary source bytes out of report JSON.
- [ ] Run the same command; require all assertions pass. Record parser/runtime version without assuming Git object ID length is 40.
- [ ] Commit the task after verification when working in a Git checkout. If subsequent implementation work includes repository setup in this currently non-Git directory, initialize it as routine authorized preparation before task commits; do not fabricate commit evidence.

### Task 2: Trusted declarative policy

**Files:** `src/pullraptor/config.py`, `tests/test_config.py`, `tests/helpers.py`.

**Consumes:** Config/Limits from Task 1.

**Produces:** `load_config(policy_bytes: bytes | None, overrides: dict[str, object], *, ci: bool) -> Config`; `matches_path(path: str, patterns: tuple[str, ...]) -> bool`. Caller supplies base-tip bytes in CI. Helpers provide `make_repo(files: dict[str, bytes]) -> FixtureRepo` with `commit(changes: dict[str, bytes | None]) -> str` and read-only commit IDs.

- [ ] Write `test_defaults_exact` asserting the limits/profile above; `test_unknown_key_error`; `test_glob_semantics` asserting `*` follows `fnmatchcase`, `**` has no special meaning, and separators normalize to `/`; `test_ci_override_cannot_weaken_required_scope`.
- [ ] Run `PYTHONPATH=src python3.12 -m unittest tests.test_config -v`; verify failure.
- [ ] Implement TOML parsing/validation and explicit precedence. Default source suffix inventory is `.py,.pyi,.js,.jsx,.ts,.tsx,.go,.rs,.java,.cs,.c,.h,.cpp,.hpp,.cc,.php,.rb,.swift,.kt,.kts,.scala,.sh,.sql`; every file still receives generic inventory. Do not import or evaluate configuration code. Policy changes in head are displayed as changes only.
- [ ] Run tests; require invalid/weakening configuration to fail with exit-class 3 rather than silently fall back.
- [ ] Commit verified policy behavior.

### Task 3: Safe immutable snapshots and exact diff facts

**Files:** `src/pullraptor/git_snapshot.py`, `src/pullraptor/diff.py`, `tests/test_snapshot.py`, `tests/test_diff.py`.

**Consumes:** Limits, Snapshot, Change and Diagnostic.

**Produces:** `resolve_inputs(repo: Path, base_ref: str, head_ref: str, *, exact_base: bool) -> tuple[str, str, str]` returning base tip/comparison base/head; `read_snapshot(repo: Path, oid: str, limits: Limits) -> Snapshot`; `read_blob(repo: Path, blob_oid: str, limits: Limits) -> bytes`; `changes(repo: Path, base_oid: str, head_oid: str) -> tuple[Change, ...]`. Provide fixed sanitized Git invocations shared only inside this boundary.

- [ ] Write `test_merge_base_not_base_tip`, `test_refs_pinned_before_read`, `test_dirty_tree_ignored`, `test_shallow_missing_object_incomplete`, `test_multiple_merge_bases_rejected` and `test_replace_objects_ignored`.
- [ ] Write `test_nul_metadata_paths` for spaces/tab/newline; `test_non_utf8_path_reported`; `test_symlink_and_submodule_not_followed`; `test_binary_and_deleted_file_preserved`; `test_hostile_external_diff_textconv_fsmonitor_not_executed`. The hostile test config points to a sentinel-writing script; sentinel must remain absent.
- [ ] Run `PYTHONPATH=src python3.12 -m unittest tests.test_snapshot tests.test_diff -v`; verify failure.
- [ ] Implement commit-only validation, merge-base ambiguity checks, NUL metadata, bounded blob reads, disabled external helpers/replacement objects, fixed argument arrays and no shell. Enforce tree-entry limits here; Task 7 enforces total analyzed-source bytes after applying the configured suffix/scope inventory. Use Git patches only for exact hunk/line mapping; do not parse display-quoted filenames to establish identity. Separate original path bytes from display/path encoding diagnostics.
- [ ] Run both modules; require correct left/right hunk spans, explicit over-limit diagnostics and no source execution. Fetching is absent from this interface.
- [ ] Commit verified ingestion behavior.

### Task 4: Bounded Python facts and explicit capabilities

**Files:** `src/pullraptor/python_facts.py`, `src/pullraptor/parser_worker.py`, `tests/test_python_facts.py`, `tests/fixtures/python/`.

**Consumes:** Blob bytes, path, side and Limits.

**Produces:** `extract_python(source: bytes, path: str, side: str, limits: Limits) -> FactResult`; `resolve_context(facts: tuple[PythonFacts, ...], manifest: Snapshot) -> tuple[tuple[PythonFacts, ...], tuple[Diagnostic, ...]]`. Resolution is recomputed each run. Worker protocol is one bounded JSON request/response, with input source encoded explicitly and no network/tools.

- [ ] Write `test_unicode_columns_crlf_exact`, `test_scope_shadowing_and_aliases`, `test_nested_functions_not_outer_mutation`, `test_parameter_reassignment`, `test_missing_import_diagnostic`, `test_new_module_resolves_previous_miss`, and `test_parse_failure_preserves_diff_coverage`.
- [ ] Write `test_timeout_or_worker_crash_partial`, `test_import_side_effect_not_executed`, and `test_oversized_source_not_sent_to_worker`. Use a trusted test worker that stalls/crashes to test deadline behavior; do not rely on flaky timing of a huge real AST.
- [ ] Run `PYTHONPATH=src python3.12 -m unittest tests.test_python_facts -v`; verify failure.
- [ ] Implement isolated stdlib parsing with encoding detection, lexical binding facts, source byte spans, local/import resolution and unsupported-construct diagnostics. Parse all required supported context, conservatively re-resolve against the current full manifest. No symbol inference from string similarity, no runtime import, no CFG/taint claim.
- [ ] Run tests; exact diagnostic shape is `PullRaptor: PY_PARSE_FAILED path:line: Python <runtime-major.minor> could not parse this file; semantic review skipped.` Parsing and scope coverage remain separate fields. AST version differences are recorded and tested on every runtime claimed supported.
- [ ] Commit verified facts and worker boundary.

### Task 5: Small advisory rule pack

**Files:** `src/pullraptor/rules.py`, `tests/test_rules.py`, `tests/fixtures/rules/`.

**Consumes:** fully current PythonFacts, trusted Config and Snapshot identity.

**Produces:** `evaluate_rules(facts: tuple[PythonFacts, ...], snapshot: Snapshot, config: Config) -> tuple[Finding, ...]`. Initial findings have no delta until Task 6.

- [ ] Write at least 10 positive and 10 negative/ambiguous fixtures per rule with expected claim/evidence/blocking status. Pin `test_intentional_patterns_never_defect_claim`, `test_shadowed_subprocess_no_shell_claim`, `test_conditional_reraise_not_classified_as_swallowed`, and `test_untrusted_command_not_inferred_from_shell_true`.
- [ ] Run `PYTHONPATH=src python3.12 -m unittest tests.test_rules -v`; verify failure.
- [ ] Implement PY001 for list/dict/set literals, direct subscript writes, and unreassigned parameter calls to list `append/extend/insert/pop/remove/clear/sort/reverse`, dict `update/setdefault/pop/popitem/clear`, or set `add/update/remove/discard/pop/clear`. Recognize these only for the known literal type. Exclude alias-mediated writes and nested scopes. Unknown prior rebinding stops the claim.
- [ ] Implement PY002 only for a bare handler whose body is straight-line operations with optional terminal `return` and no `raise`; nested/branching control flow is unclassified. Implement PY003 only for resolved `subprocess.run/Popen/call/check_call/check_output` with literal true shell keyword. Attach exact witnesses, stated consequences, rule version and advisory class. Never recommend replacing a mutable default without considering the intended API semantics.
- [ ] Run fixtures; all initial findings must be advisory and satisfy their exact factual predicates. No shell pattern may contain an injection/exploit assertion.
- [ ] Commit verified rules.

### Task 6: Evidence, alignment and policy decisions

**Files:** `src/pullraptor/evidence.py`, `tests/test_evidence.py`.

**Consumes:** both snapshot rule outputs and their coverage/config/version records.

**Produces:** `accumulate(evidence: tuple[Evidence, ...]) -> tuple[bool, bool]`; `align_findings(base: tuple[Finding, ...], head: tuple[Finding, ...], *, comparable: bool) -> tuple[Finding, ...]`; `decide(findings: tuple[Finding, ...], coverage: tuple[Coverage, ...], diagnostics: tuple[Diagnostic, ...], config: Config) -> int`.

- [ ] Write `test_all_evidence_accumulations` over all 16 pair combinations; `test_different_claim_or_revision_cannot_accumulate`; `test_conflict_not_blocker`; `test_shifted_line_same_obligation`; `test_ambiguous_rename_unknown`; `test_base_parse_failure_delta_unknown`; `test_old_sink_new_witness_retained`; `test_incomplete_precedes_finding_exit`; `test_fatal_diagnostic_exit3`.
- [ ] Run `PYTHONPATH=src python3.12 -m unittest tests.test_evidence -v`; verify failure.
- [ ] Implement componentwise evidence accumulation only within the same claim/snapshot/model context, conservative partial root-cause matching and independent policy evaluation. Reject attempts to merge different contexts. Match only a unique rule/version + qualified symbol + normalized obligation key in the same module; normalize relevant AST facts without position attributes. Cross-path matching requires a unique exact-blob rename correspondence; modified or multiple candidate renames remain unknown. Semantic witness comparison is separate from revision/blob binding, so shifted locations can retain an obligation while fresh evidence is rebound. New witness/obligation paths survive deduplication. Do not emit “introduced” or “fixed” from set subtraction alone. Supported pattern facts cannot satisfy a defect-blocking policy. Fatal tool/config/input diagnostics return 3; otherwise required incomplete coverage returns 2 before blocker evaluation.
- [ ] Run tests; assert canonical ordering and states. Initial default decision is 0 only when required coverage completes; otherwise 2/3 as specified.
- [ ] Commit verified evidence behavior.

### Task 7: Disposable parse cache and orchestration

**Files:** `src/pullraptor/cache.py`, `src/pullraptor/kernel.py`, `tests/test_cache.py`, `tests/test_kernel.py`.

**Consumes:** previous task interfaces.

**Produces:** `cache_key(blob_digest: str, runtime: str, schema_version: str, extractor_digest: str) -> str`; `load_facts(cache_dir: Path, key: str) -> PythonFacts | None`; `store_facts(cache_dir: Path, key: str, facts: PythonFacts, limits: Limits) -> None`; `review(repo: Path, base_ref: str, head_ref: str, overrides: dict[str, object] | None = None, *, ci: bool = False, exact_base: bool = False, use_cache: bool = True) -> Report`.

Cached facts are content-only with no trusted occurrence path/side; rebind spans to the current manifest occurrence on load. If fact extraction later uses configuration, extend the key with the relevant digest before reuse. Rules and context resolution are always rerun in E01. Kernel review resolves refs once, reads `.pullraptor.toml` from the pinned base tip, then calls `load_config`; it never accepts an already-loaded policy of unknown origin. The extractor digest covers the trusted parser-worker implementation, so changed code cannot accidentally reuse facts merely because someone forgot to bump a schema version.

- [ ] Write `test_clean_warm_corrupt_cache_identical`, `test_atomic_interrupted_write_miss`, `test_runtime_schema_change_miss`, `test_same_blob_different_paths_rebound`, `test_size_cap`, and `test_full_manifest_resolution_recomputed`.
- [ ] Add mutation sequences: rename, delete a dependency, add a previously missing module, alter policy, move a witness, exceed a limit and recover. For every completed analysis assert full canonical equality between cache-enabled and no-cache runs. Separately inject cold deadline exhaustion and warm completion, assert visible partial/complete receipts, then compare after a complete clean replay.
- [ ] Run `PYTHONPATH=src python3.12 -m unittest tests.test_cache tests.test_kernel -v`; verify failure.
- [ ] Implement atomic bounded cache outside reviewed trees and the pipeline. Keep path/side reattachment explicit. Load source only as needed, honor the total deadline and retain coverage for unfinished work. Rebuild both revision outputs before alignment. Resolve configuration from base tip, not head or merge base.
- [ ] Run both modules; validate no raw source/model data in cache, no execution metadata in canonical comparison, and no stale lookup reuse.
- [ ] Commit verified orchestration.

### Task 8: CLI, formats and user-path acceptance

**Files:** `src/pullraptor/__main__.py`, `src/pullraptor/render.py`, `tests/test_cli.py`, `tests/test_render.py`, `tests/fixtures/e2e/`; update `README.md` with actually supported usage only.

**Consumes:** review/decide and Report.

**Produces:** `render_markdown(report: Report) -> str`; `render_json(report: Report) -> str`; `render_sarif(report: Report) -> str`; `main(argv: list[str] | None = None) -> int`.

- [ ] Write `test_structural_python_complete`, `test_structural_other_language_partial_exit2`, `test_explicit_diff_profile_scope_statement`, `test_config_error_exit3`, `test_empty_findings_not_safety_claim`, `test_deleted_line_sarif_side`, `test_unicode_sarif_character_columns`, and `test_stdout_machine_format_stderr_diagnostics`.
- [ ] Add `test_core_network_disabled` by denying sockets/DNS during an end-to-end run, and rerun sentinel Git/source-execution cases through the CLI. Every report includes comparison identities and coverage.
- [ ] Run `PYTHONPATH=src python3.12 -m unittest tests.test_cli tests.test_render -v`; verify failure.
- [ ] Implement `review --base --head --exact-base --profile structural|diff --format markdown|json|sarif --no-cache`, explicit output/error behavior, concise walkthrough and side-aware findings. Reject unsupported Python minor runtimes at startup. Task 4 computes decoded-character columns; SARIF rendering uses them without rereading the tree. Current-head alerts alone enter SARIF `results`; removed/baseline-only findings remain in the report/history run properties with baseline identity. Include partial status in every format.
- [ ] Run `PYTHONPATH=src python3.12 -m unittest discover -s tests -v`. Manually run the three documented commands on pinned positive/negative/mixed-language fixture repositories. Save exact outputs and exit codes.
- [ ] Measure cold/warm time and RSS against the documented fixture; report actual values even if targets fail. Audit imports, subprocesses, file/module count and runtime requirements. Verify competitor-name/domain absence and all local documentation links.
- [ ] Perform whole-kernel review of trust boundaries, adverse inputs and scope claims. Record limitations, update E01 status only with acceptance evidence, and commit verified deliverable. Do not begin E02–E06 without their child plans.

## Handoff

No production tasks are complete. When implementation is authorized, sequential task implementation with independent review is recommended because ingestion, scope, and evidence interfaces share security-sensitive invariants. Parallel research or independent fixture preparation can continue, but shared kernel interfaces should stabilize in task order. Any new dependency or semantic capability must earn a scoped design decision and acceptance gate.
