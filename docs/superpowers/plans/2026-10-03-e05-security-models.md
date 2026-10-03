# E05: Bounded security models and external observations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce narrow, evidence-labeled security observations without claiming universal exploitability.

**Architecture:** Use finite value/location hazard maps, monotone worklists and witnessed predecessor edges; unknown calls conservatively propagate hazards and add boundary records. Authorization is a separate must-analysis over subject/action/resource/state facts, using intersections over all modeled may-feasible predecessors. Add frozen SecurityModel(version, sources, sinks, sanitizer_contexts, external_summaries, limits), SecurityObservation(claim, rule, model_version, span, witnesses, assumptions, boundaries), and ImportedObservation(producer, version, revision, claim, span, trust). All outputs are advisory observations/proposals until matching trusted evidence supports their precise claim.

**Tech Stack:** Python 3.12 stdlib/unittest; owned CFG/dataflow algorithms; optional allowlisted advisory connector outside the kernel.

**Spec:** [E05 child specification](../specs/2026-10-03-e05-security-models.md).

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

1. Sanitizing one value cannot clean the original or the wrong hazard (Task 1).
2. An alternate path, wrong resource or reassigned subject cannot establish authorization (Task 2).
3. Unknown calls and loop/alias truncation cannot imply safety (Tasks 1–2).
4. Secrets and hostile scanner links must remain redacted inert data (Tasks 3–4).
5. Stale advisories or same-version data from another ecosystem cannot imply an affected runtime (Task 4).

## File and interface map

- Task 1: create `src/pullraptor/python_cfg.py`, `src/pullraptor/security_flow.py`; modify `src/pullraptor/kernel.py`; bounded graph construction and monotone transfers.
- Task 2: create `src/pullraptor/auth_obligations.py`; separate authorization model.
- Task 3: create `src/pullraptor/secret_patterns.py`; modify `src/pullraptor/render.py`; owned advisory detection with value-free output.
- Task 4: create `src/pullraptor/advisories.py`, `src/pullraptor/scanner_import.py`; external data provenance without evidence promotion.

### Task 1: Own finite Python CFG and value-specific hazard propagation

**Acceptance:** E05-A1.

**Files:** create `src/pullraptor/python_cfg.py`, `src/pullraptor/security_flow.py`; modify `src/pullraptor/kernel.py`; test: `tests/test_security_flow.py`.

**Interfaces:**
- Consumes: bound Python AST facts, ReviewContract, Limits, Deadline and SecurityModel.
- Produces: `build_cfg(facts: BoundFacts, model: SecurityModel) -> ControlFlow`; ControlFlow(entry, nodes, edges, complete, boundaries); `analyze_hazards(cfg: ControlFlow, model: SecurityModel, deadline: Deadline) -> FlowResult`; FlowResult(observations: tuple[SecurityObservation, ...], complete: bool, boundaries: tuple[str, ...]).

- [ ] **Step 1: Write the failing acceptance tests.** Add `test_sanitizer_only_return_value`, `test_wrong_context_sanitizer`, `test_ambiguous_alias_weak_update`, `test_unknown_call_propagates`, `test_loop_monotone_converges`, and `test_transfer_cap_partial`. For `a=source(); b=sql_escape(a); execute_sql(a)`, a SQL hazard survives on a; b's sanitizer does not discharge shell/filesystem hazards. Include 30 positive and 30 negative/unknown held-out cases per advertised model.

Expected assertions for the stated adverse fixture:

```python
assert "sql" in hazards_at_sink["a"]
assert truncated.complete is False
```

- [ ] **Step 2: Run the focused suite and confirm a meaningful failure.** Run `PYTHONPATH=src python3.12 -m unittest tests.test_security_flow -v`. Missing new interfaces may fail import initially; existing code must fail the new adverse assertion before correction.
- [ ] **Step 3: Implement the declared interfaces.** Implement the spec's exact initial PYSEC001 input-to-shell model; SQL/filesystem sanitizer cases are synthetic transfer tests, not advertised production detectors. Define an explicit supported straight-line/branch/loop/exception subset and finite locations; emit boundaries for unsupported constructs. Strong updates require one target, otherwise weak update or unknown. Store witnessed value correspondence, deterministic worklist ordering and all model/config identities. Do not execute functions or infer path feasibility from missing edges.
- [ ] **Step 4: Run the same suite.** Require all named assertions to pass, including the successful fixture; retain raw outputs and exact input/tool identities.
- [ ] **Step 5: Commit the reviewed task on an allowed feature branch.** Stage only this task's files; use commit message `feat: add bounded witnessed hazard analysis`. Do not commit to `main`.

### Task 2: Evaluate authorization as must facts

**Acceptance:** E05-A2.

**Files:** create `src/pullraptor/auth_obligations.py`; test: `tests/test_auth_obligations.py`.

**Interfaces:**
- Consumes: Task 1 ControlFlow and explicit trusted AuthModel(version, entry_preconditions, checks, required_actions, invalidators).
- Produces: `analyze_authorization(cfg: ControlFlow, model: AuthModel) -> AuthorizationResult`; AuthorizationResult(observations, complete, established); established contains AuthFact(subject, action, resource, state_version).

- [ ] **Step 1: Write the failing acceptance tests.** Add `test_alternate_unauthorized_path`, `test_wrong_resource_guard`, `test_reassignment_kills_permission`, `test_fail_open_guard`, `test_disconnected_incomplete_entry`, and `test_success_branch_only_gen`. A guarded branch joined with an unchecked branch must not establish the permission; an incomplete entry cannot inherit a top initialization as proof.

Expected assertions for the stated adverse fixture:

```python
assert required_fact not in result.established
assert result.observations[0].claim == "Authorization not established by this model"
```

- [ ] **Step 2: Run the focused suite and confirm a meaningful failure.** Run `PYTHONPATH=src python3.12 -m unittest tests.test_auth_obligations -v`. Missing new interfaces may fail import initially; existing code must fail the new adverse assertion before correction.
- [ ] **Step 3: Implement the declared interfaces.** Use the spec's exact AUTH001 model identity/argument/success-branch contract. Use intersection over every may-feasible predecessor, declared entry preconditions and kill/gen transfers; generate only on the successful check branch. Preserve state/subject/resource identity and unknown invalidators. Publish assumptions and completeness separately; dominance alone is insufficient.
- [ ] **Step 4: Run the same suite.** Require all named assertions to pass, including the successful fixture; retain raw outputs and exact input/tool identities.
- [ ] **Step 5: Commit the reviewed task on an allowed feature branch.** Stage only this task's files; use commit message `feat: model bounded authorization obligations`. Do not commit to `main`.

### Task 3: Detect and redact local secret-risk patterns

**Acceptance:** E05-A3.

**Files:** create `src/pullraptor/secret_patterns.py`; modify `src/pullraptor/render.py`; test: `tests/test_secret_patterns.py`.

**Interfaces:**
- Consumes: immutable admitted text bytes and pinned SecretPattern(version, identifier, prefix, min_length, context_class) records.
- Produces: `scan_secrets(source: bytes, patterns: tuple[SecretPattern, ...]) -> tuple[SecretObservation, ...]`; SecretObservation(pattern_id, version, relative_span, redacted_label, context_class), with no secret value/digest field.

- [ ] **Step 1: Write the failing acceptance tests.** Add `test_secret_never_in_report_log_cache`, `test_examples_and_placeholders_advisory`, `test_high_entropy_not_verified_credential`, `test_unicode_location`, and `test_no_remote_probe`. The fixture's raw secret and its value-specific digest must not appear in any output/log/cache; no socket is opened.

Expected assertions for the stated adverse fixture:

```python
assert raw_secret not in serialized_report
assert value_digest not in serialized_report
assert network_calls == 0
```

- [ ] **Step 2: Run the focused suite and confirm a meaningful failure.** Run `PYTHONPATH=src python3.12 -m unittest tests.test_secret_patterns tests.test_render -v`. Missing new interfaces may fail import initially; existing code must fail the new adverse assertion before correction.
- [ ] **Step 3: Implement the declared interfaces.** Implement the spec's owned SECRET001–SECRET003 literals, assignment labels, 32/40/512-character boundaries and 4.0-bit entropy threshold; test just-below/exact/just-above boundaries and placeholders. Use only local prefix/shape/entropy/context candidates; render redacted labels and exact spans. Keep remediation text declarative and do not validate values remotely or cache secret-bearing source.
- [ ] **Step 4: Run the same suite.** Require all named assertions to pass, including the successful fixture; retain raw outputs and exact input/tool identities.
- [ ] **Step 5: Commit the reviewed task on an allowed feature branch.** Stage only this task's files; use commit message `feat: report redacted local secret-risk patterns`. Do not commit to `main`.

### Task 4: Import bounded advisories and scanner proposals

**Acceptance:** E05-A4.

**Files:** create `src/pullraptor/advisories.py`, `src/pullraptor/scanner_import.py`; test: `tests/test_security_imports.py`.

**Interfaces:**
- Consumes: trusted advisory endpoint policy, pinned lockfile bytes, bounded external records and reviewed revision.
- Produces: `match_advisories(lockfile: LockfileInventory, response: AdvisorySnapshot) -> tuple[ImportedObservation, ...]`; LockfileInventory(ecosystem, schema_version, packages), AdvisorySnapshot(origin, retrieved_at, valid_until, schema_version, entries); `import_sarif(payload: bytes, expected_revision: str, limits: RecordLimits) -> tuple[ImportedObservation, ...]`.

- [ ] **Step 1: Write the failing acceptance tests.** Add `test_ecosystem_version_exact_match`, `test_stale_advisory_unknown`, `test_wrong_revision_sarif_rejected`, `test_link_command_fix_fields_inert`, `test_duplicate_json_nonfinite_rejected`, and `test_offline_no_lookup`. Initially support explicit `package-lock.json` schema 3 and pinned Python lock inventory format 1; unsupported schemas remain gaps. Import SARIF 2.1.0 results/message/ruleId/physicalLocation plus producer/version and explicit revision provenance; unsupported active fields cannot be applied.

Expected assertions for the stated adverse fixture:

```python
assert stale_observation.trust == "stale"
assert source_uploaded_bytes == 0
assert executed_import_commands == ()
```

- [ ] **Step 2: Run the focused suite and confirm a meaningful failure.** Run `PYTHONPATH=src python3.12 -m unittest tests.test_security_imports -v`. Missing new interfaces may fail import initially; existing code must fail the new adverse assertion before correction.
- [ ] **Step 3: Implement the declared interfaces.** Parse declarative version/ecosystem inventories without project installation. Use operator-approved HTTPS and actual-address egress enforcement, no proxies/redirects; cache timestamped advisory data separately from parser facts. Missing revision provenance is rejected for exact-review import. Preserve scanner trust; matching installed version does not prove exploitability or reachable code.
- [ ] **Step 4: Run the same suite.** Require all named assertions to pass, including the successful fixture; retain raw outputs and exact input/tool identities.
- [ ] **Step 5: Commit the reviewed task on an allowed feature branch.** Stage only this task's files; use commit message `feat: import revision-bound security observations`. Do not commit to `main`.

## Package acceptance and handoff

- [ ] Re-run this package's focused suites and the affected existing suites in the trusted development environment; reviewed-source execution uses only an accepted runner.
- [ ] Exercise the scoped install/connect → exact review → visible coverage → repeat after changes → revoke/uninstall flow where this package exposes a delivery surface.
- [ ] Record all E05-A1 through E05-A4 criteria, dependency/license inventory and actual resource measurements in `docs/acceptance/E05.md`.
- [ ] Obtain independent acceptance review. Until then retain the actual implementation state and acceptance pending in the master plan. Accepted subsets do not mark the broader package complete.
