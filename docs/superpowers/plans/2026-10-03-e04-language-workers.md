# E04: Declared language workers and capability admission Implementation Plan

**Build handoff:** [task board](../../build-task-board.md), [exact task cards](../../build-tasks.json) and [coordinator interface decisions](../../build-interfaces.md). Read these with this plan; distinguish reviewed-output construction prerequisites from activation/acceptance gates.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Admit optional language facts with per-language capability and quality evidence.

**Architecture:** Own the coordinator and rule algorithms. Add frozen LanguageRequest(contract_digest, scope_keys, language, grammar_digest, capability, source_blobs) and LanguageResult(contract_digest, completed_keys, content_facts, unsupported, producer_digest). An operator-owned registry maps language/capability to pinned trusted executable and explicit environment. Validate worker results independently against requested scope; workers never pick their own completeness.

**Tech Stack:** Python stdlib coordinator and unittest; optional pinned language parser workers outside the kernel. Go worker may use go/parser; JS/TS worker may use a licensed parser API after inventory/admission.

**Spec:** [E04 child specification](../specs/2026-10-03-e04-language-workers.md).

**Status:** Proposed; all tasks below are unexecuted. Read the spec and [execution gate](../../planning-contract.md) before starting. Existing artifacts are inputs to audit, not accepted implementations of the expanded scope.

## Global Constraints

- Zero third-party packages in the deterministic kernel; Git executable required.
- Python 3.12.x pinned baseline; versions 3.13+ / 3.14+ admitted only after AST parser parity verification.
- Keep competing product names out of all project files.
- Apply the [execution and acceptance contract](../../planning-contract.md); these are proposed tasks, not execution authorization.
- Trusted base policy and coordinator-owned scope are authoritative; unknown/incomplete/conflicted/stale results stay visible.
- Never execute reviewed code in the analysis process; optional execution requires the separately accepted E06 runner.
- No ambient worker credentials, foreign/shared caches, automatic dependency installation or automatic merge.

## Review Focus

1. A grammar-only worker cannot advertise CFG/dataflow (Task 1).
2. Malformed/version-new syntax returns an explicit capability gap (Task 2).
3. Module aliases, macros and reflection must abstain where unsupported (Task 3).
4. Deleted edges and new formerly missing modules must match a clean replay (Tasks 1 and 3).
5. Timeout or omitted/duplicate foreign receipts cannot shrink coordinator scope (Task 1).

## File and interface map

- Task 1: create `src/pullraptor/language_workers.py`; modify `src/pullraptor/kernel.py`, `src/pullraptor/process.py`; test `tests/test_process.py`; trusted registry and coordinator receipt validation.
- Task 2: create `workers/typescript/worker.mjs`, `workers/go/main.go`, `tests/fixtures/languages/js_ts/`, `tests/fixtures/languages/go/`; bounded syntax and lexical structure only.
- Task 3: create `docs/language-capabilities.json`, `src/pullraptor/graph_view.py`, `tests/fixtures/languages/wave_two/`, `tests/fixtures/languages/wave_three/`; extend `src/pullraptor/language_workers.py`; per-language rollout and safe owned graph serialization.

### Task 1: Define and validate worker contracts

**Acceptance:** E04-A1.

**Files:** create `src/pullraptor/language_workers.py`; modify `src/pullraptor/kernel.py`, `src/pullraptor/process.py`; test: `tests/test_language_workers.py`, `tests/test_process.py`. E04-D0 owns the bounded stdin extension; pure result validators do not wait for a live parser.

**Interfaces:**
- Consumes: ReviewContract, ContentFacts, CoverageReceipt, Limits, Deadline and existing bounded codec helper and E04-D0 bounded stdin contract in the [coordinator interface decisions](../../build-interfaces.md). The current process helper has DEVNULL stdin; a JSON worker request needs the explicit optional input/cap extension before real dispatch.
- Produces: `run_language(request: LanguageRequest, *, registry: LanguageRegistry, limits: Limits, deadline: Deadline) -> LanguageResult`; LanguageRegistry is an immutable tuple of entries(language, capability, executable_digest, grammar_digest, allowed_environment).

- [ ] **Step 1: Write the failing acceptance tests.** Add `test_omitted_foreign_duplicate_receipts_partial`, `test_worker_cannot_advertise_extra_capability`, `test_grammar_config_change_invalidates_cache`, `test_source_not_executed`, and `test_timeout_has_gap`. An omitted required key remains a coordinator gap and cannot produce completed coverage.

Expected assertions for the stated adverse fixture:

```python
assert missing_key not in result.completed_keys
assert "missing_receipt" in result.unsupported
```

- [ ] **Step 2: Run the focused suite and confirm a meaningful failure.** Run `PYTHONPATH=src python3.12 -m unittest tests.test_language_workers tests.test_kernel -v`. Missing new interfaces may fail import initially; existing code must fail the new adverse assertion before correction.
- [ ] **Step 3: Implement the declared interfaces.** Reuse strict decoding and shared process bounds; registry comes from trusted policy, never source. Cache only occurrence-free facts with all producer/config identities, then recompute resolution. Preserve old and new lookup domains or fully redo resolution. Optional components cannot change core imports.
- [ ] **Step 4: Run the same suite.** Require all named assertions to pass, including the successful fixture; retain raw outputs and exact input/tool identities.
- [ ] **Step 5: Commit the reviewed task on an allowed feature branch.** Stage only this task's files; use commit message `feat: validate optional language worker results`. Do not commit to `main`.

### Task 2: Deliver the first JS/TS and Go structure wave

**Acceptance:** E04-A2.

**Files:** create `workers/typescript/worker.mjs`, `workers/go/main.go`, `tests/fixtures/languages/js_ts/`, `tests/fixtures/languages/go/`; test: `tests/test_language_wave_one.py`.

**Interfaces:**
- Consumes: Task 1 request/result records and admitted pinned parser/runtime inventories.
- Produces: worker protocol v1; advertised initial capabilities `syntax` and `structure` only, with relative byte/character spans and unsupported-construct records.

- [ ] **Step 1: Write the failing acceptance tests.** Add `test_js_ts_version_syntax_gap`, `test_go_generated_and_build_tags_declared`, `test_unicode_spans`, `test_alias_shadowing_abstains`, and `test_no_calls_cfg_dataflow_claim`. Use at least 30 held-out positive and 30 negative/unknown cases per advertised capability/language and licensed real repositories. For new unsupported grammar, complete syntax is false; there are no invented CFG facts.

Expected assertions for the stated adverse fixture:

```python
assert "cfg" not in advertised_capabilities
assert unsupported_version_key not in result.completed_keys
```

- [ ] **Step 2: Run the focused suite and confirm a meaningful failure.** Run `PYTHONPATH=src python3.12 -m unittest tests.test_language_wave_one -v`. Missing new interfaces may fail import initially; existing code must fail the new adverse assertion before correction.
- [ ] **Step 3: Implement the declared interfaces.** Translate admitted parser results into owned content facts; do not run module resolution/build hooks from the reviewed project. Pin version and source extensions, keep TS/JS distinctions visible, and admit one language/capability at a time. Add startup/RSS/size and clean/incremental measurements.
- [ ] **Step 4: Run the same suite.** Require all named assertions to pass, including the successful fixture; retain raw outputs and exact input/tool identities.
- [ ] **Step 5: Commit the reviewed task on an allowed feature branch.** Stage only this task's files; use commit message `feat: add evaluated first language worker wave`. Do not commit to `main`.

### Task 3: Admit later languages and bounded relationship presentation

**Acceptance:** E04-A3.

**Files:** create `docs/language-capabilities.json`, `src/pullraptor/graph_view.py`, `tests/fixtures/languages/wave_two/`, `tests/fixtures/languages/wave_three/`; extend `src/pullraptor/language_workers.py`; test: `tests/test_language_admission.py`.

**Interfaces:**
- Consumes: Task 1 registry/results; independently pinned parser candidates for Java/C#, then Rust/PHP/Ruby/C/C++.
- Produces: `admit_capability(matrix: CapabilityMatrix, evidence: CapabilityEvidence) -> CapabilityMatrix`; immutable rows(language, grammar_version, capability, state, evidence_path), CapabilityEvidence includes dataset_revision, positives, negatives_unknown, independent_labels and measurements; `render_graph(nodes: tuple[GraphNode, ...], edges: tuple[GraphEdge, ...]) -> str` with GraphNode(id, label) and GraphEdge(source_id, target_id, relation, certainty).

- [ ] **Step 1: Write the failing acceptance tests.** Add `test_syntax_pass_does_not_admit_dataflow`, `test_each_language_independent`, `test_reflection_macro_unknown`, `test_deleted_edge_new_lookup_clean_equivalence`, and `test_diagram_syntax_uri_breakout`. Each later language repeats Task 2's ≥30/≥30 and real-repository gate for each claimed capability; insufficient evidence leaves state `proposed`. Hostile labels cannot supply Mermaid syntax or URLs.

Expected assertions for the stated adverse fixture:

```python
assert matrix.row("Java", "dataflow").state == "proposed"
assert source_supplied_node_id not in diagram
```

- [ ] **Step 2: Run the focused suite and confirm a meaningful failure.** Run `PYTHONPATH=src python3.12 -m unittest tests.test_language_admission -v`. Missing new interfaces may fail import initially; existing code must fail the new adverse assertion before correction.
- [ ] **Step 3: Implement the declared interfaces.** Create a pending row for every named language/capability and execute the admission cycle separately for Java, C#, Rust, PHP, Ruby, C and C++; specify each parser's exact optional path/digest/license in the registry before code admission. This is not permission to fabricate full-language semantics. Use opaque generated node IDs and escaped bounded labels; missing edges and cycles fall back to a file walkthrough. Calls/CFG/dataflow/auth stay unavailable until their own model and corpus evidence passes.
- [ ] **Step 4: Run the same suite.** Require all named assertions to pass, including the successful fixture; retain raw outputs and exact input/tool identities.
- [ ] **Step 5: Commit the reviewed task on an allowed feature branch.** Stage only this task's files; use commit message `feat: gate language capabilities and graph presentation`. Do not commit to `main`.

## Package acceptance and handoff

- [ ] Re-run this package's focused suites and the affected existing suites in the trusted development environment; reviewed-source execution uses only an accepted runner.
- [ ] Exercise the scoped install/connect → exact review → visible coverage → repeat after changes → revoke/uninstall flow where this package exposes a delivery surface.
- [ ] Record all E04-A1 through E04-A3 criteria, dependency/license inventory and actual resource measurements in `docs/acceptance/E04.md`.
- [ ] Obtain independent acceptance review. Until then retain the actual implementation state and acceptance pending in the master plan. Accepted subsets do not mark the broader package complete.
