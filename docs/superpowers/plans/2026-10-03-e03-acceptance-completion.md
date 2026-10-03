# E03: AI context, transport and conversation acceptance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the broader E03 contract while retaining AI output as optional untrusted proposals.

**Architecture:** Add frozen ContextBlock(id, kind, producer, source_revision, digest, serialized_bytes, mandatory, priority), ContextManifest(report_digest, head, blocks, retrieval_receipts), AIInvocationReceipt(requests_used, context_bytes, requested_output_tokens, elapsed_seconds, cost_state), and Conversation(report_digest, head, context_manifest, turns). AIReviewEnvelope(schema='ai-review/1', report, proposals, context_manifest, invocation_receipt) wraps rather than silently changes report schema 1. AIProposal remains typed untrusted content with producer/context provenance and no authority fields.

**Tech Stack:** Python 3.12 stdlib/unittest; provider-neutral HTTPS adapter and explicit local-provider profile outside deterministic kernel.

**Spec:** [E03 child specification](../specs/2026-10-03-e03-acceptance-completion.md).

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

1. CI logs from another head or model-invented references cannot support this report (Task 1).
2. Mandatory context over budget must abstain, not trim a security witness (Task 1).
3. DNS rebinding, proxies and redirects cannot redirect credentials/source (Task 2).
4. Issue/source/model instructions cannot change policy, destinations or budgets (Tasks 1–3).
5. Later head/chat context and repeated model allegations cannot erase counterevidence or clear findings (Task 3).

## File and interface map

- Task 1: modify `src/pullraptor/ai_adapter.py`, `src/pullraptor/__main__.py`; create `src/pullraptor/ai_context.py`; context provenance, redaction and preview.
- Task 2: modify `src/pullraptor/ai_adapter.py`; create `src/pullraptor/ai_transport.py`; destination/address enforcement and usage receipts.
- Task 3: create `src/pullraptor/conversation.py`; modify `src/pullraptor/render.py`, `src/pullraptor/__main__.py`; bounded read-only sessions and proposal presentation.

### Task 1: Pin and select bounded mandatory context

**Acceptance:** E03-A1.

**Files:** modify `src/pullraptor/ai_adapter.py`, `src/pullraptor/__main__.py`; create `src/pullraptor/ai_context.py`; test: `tests/test_ai_context.py`.

**Interfaces:**
- Consumes: exact report/head, bounded issue/CI retrieval receipts and trusted context priorities.
- Produces: `select_context(manifest: ContextManifest, budget_bytes: int) -> ContextSelection`; ContextSelection(block_ids, serialized_bytes, state, cause), plus frozen context records from the spec.

- [ ] **Step 1: Write the failing acceptance tests.** Add `test_stale_ci_log_rejected`, `test_issue_revision_bound`, `test_mandatory_guard_over_budget_abstains`, `test_utf8_serialized_cost_exact`, `test_context_preview_redacted`, and `test_injected_config_inert`. For mandatory content exceeding 65,536 bytes, select no partial security witness and return unavailable with cause `mandatory_context_over_budget`.

Expected assertions for the stated adverse fixture:

```python
assert selection.state == "unavailable"
assert selection.cause == "mandatory_context_over_budget"
assert outbound_requests == 0
```

- [ ] **Step 2: Run the focused suite and confirm a meaningful failure.** Run `PYTHONPATH=src python3.12 -m unittest tests.test_ai_context tests.test_ai_adapter -v`. Missing new interfaces may fail import initially; existing code must fail the new adverse assertion before correction.
- [ ] **Step 3: Implement the declared interfaces.** Bind issue provider/ID/revision and CI provider/run/job/head identities through connector receipts, mark absent/stale provenance, and price exact serialized bytes. Admit mandatory witnesses first; use deterministic priority/cost greedy selection with stable ID ties afterward. Preview transmitted paths/bytes/destinations and redact values without claiming guaranteed remote privacy.
- [ ] **Step 4: Run the same suite.** Require all named assertions to pass, including the successful fixture; retain raw outputs and exact input/tool identities.
- [ ] **Step 5: Commit the reviewed task on an allowed feature branch.** Stage only this task's files; use commit message `feat: pin bounded AI context manifests`. Do not commit to `main`.

### Task 2: Enforce explicit provider transport and invocation budgets

**Acceptance:** E03-A2.

**Files:** modify `src/pullraptor/ai_adapter.py`; create `src/pullraptor/ai_transport.py`; test: `tests/test_ai_transport.py`.

**Interfaces:**
- Consumes: Task 1 ContextSelection and ProviderPolicy(profile, approved_origin, approved_path, permitted_addresses, credential_reference, spend_cap, retention_policy).
- Produces: `invoke_provider(context: ContextSelection, policy: ProviderPolicy, budget: AIBudget) -> AIResult`; AIBudget(max_requests, context_bytes, output_tokens, deadline), AIResult(proposals, receipt, state, cause).

- [ ] **Step 1: Write the failing acceptance tests.** Add `test_proxy_environment_ignored`, `test_redirect_not_followed`, `test_actual_address_mismatch_denied`, `test_remote_private_address_denied`, `test_explicit_local_profile`, `test_retries_share_budget`, and `test_output_authority_fields_rejected`. A connected-address mismatch produces transport_denied before source/credentials are sent.

Expected assertions for the stated adverse fixture:

```python
assert result.state == "transport_denied"
assert sent_context_bytes == 0
assert sent_credentials is False
```

- [ ] **Step 2: Run the focused suite and confirm a meaningful failure.** Run `PYTHONPATH=src python3.12 -m unittest tests.test_ai_transport tests.test_ai_adapter -v`. Missing new interfaces may fail import initially; existing code must fail the new adverse assertion before correction.
- [ ] **Step 3: Implement the declared interfaces.** Use authenticated TLS to the explicit origin/path with no ambient proxy/redirect; enforce actual connected-address allowlisting or an accepted OS egress rule. Separate local/private-provider policy from remote. Track 2-request/65,536-byte/2,048-output-token/60-second totals including retries and cost_unknown. Strictly decode bounded proposal output and reject support/permission/publication/destination fields.
- [ ] **Step 4: Run the same suite.** Require all named assertions to pass, including the successful fixture; retain raw outputs and exact input/tool identities.
- [ ] **Step 5: Commit the reviewed task on an allowed feature branch.** Stage only this task's files; use commit message `feat: enforce AI transport and budget receipts`. Do not commit to `main`.

### Task 3: Ground explanation, challenge and drafts in report identity

**Acceptance:** E03-A3.

**Files:** create `src/pullraptor/conversation.py`; modify `src/pullraptor/render.py`, `src/pullraptor/__main__.py`; test: `tests/test_conversation.py`.

**Interfaces:**
- Consumes: Task 1 ContextManifest, Task 2 AIResult and immutable report evidence.
- Produces: `answer(conversation: Conversation, question: str, current_report_digest: str) -> ConversationAnswer`; ConversationAnswer(state, text, evidence_refs, proposals, counterevidence_requests); AIReviewEnvelope from spec keeps report unchanged.

- [ ] **Step 1: Write the failing acceptance tests.** Add `test_head_or_context_change_stale`, `test_conflict_preserved`, `test_fake_location_not_supported`, `test_test_doc_draft_not_executed`, `test_20_turn_limit`, `test_ai_disabled_no_network`, and `test_canonical_findings_unchanged`. A new head makes the old session stale and sends no provider request; dismissal/model assertion does not remove support/refutation.

Expected assertions for the stated adverse fixture:

```python
assert answer_result.state == "stale"
assert original_canonical == envelope.report_canonical
assert generated_tests_executed == 0
```

- [ ] **Step 2: Run the focused suite and confirm a meaningful failure.** Run `PYTHONPATH=src python3.12 -m unittest tests.test_conversation tests.test_render -v`. Missing new interfaces may fail import initially; existing code must fail the new adverse assertion before correction.
- [ ] **Step 3: Implement the declared interfaces.** Use deterministic rule explanations when AI is disabled, label behavioral answers/drafts untrusted, retain citations to exact report witnesses and request fresh analysis when contradictory data cannot be validated. Render proposal text through owned escaping. Expose suggestions as drafts and hand patch proposals to E06 for validation; model output cannot clear an obligation or publish.
- [ ] **Step 4: Run the same suite.** Require all named assertions to pass, including the successful fixture; retain raw outputs and exact input/tool identities.
- [ ] **Step 5: Commit the reviewed task on an allowed feature branch.** Stage only this task's files; use commit message `feat: ground review conversations in pinned reports`. Do not commit to `main`.

## Package acceptance and handoff

- [ ] Re-run this package's focused suites and the affected existing suites in the trusted development environment; reviewed-source execution uses only an accepted runner.
- [ ] Exercise the scoped install/connect → exact review → visible coverage → repeat after changes → revoke/uninstall flow where this package exposes a delivery surface.
- [ ] Record all E03-A1 through E03-A3 criteria, dependency/license inventory and actual resource measurements in `docs/acceptance/E03.md`.
- [ ] Obtain independent acceptance review. Until then retain the actual implementation state and acceptance pending in the master plan. Accepted subsets do not mark the broader package complete.
