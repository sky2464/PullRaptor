# E08: Editor, plugin and local/remote MCP delivery acceptance Implementation Plan

**Build handoff:** [task board](../../build-task-board.md), [exact task cards](../../build-tasks.json) and [coordinator interface decisions](../../build-interfaces.md). Read these with this plan; distinguish reviewed-output construction prerequisites from activation/acceptance gates.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the existing MCP/manifest subset into accepted installable editor and assistant surfaces.

**Architecture:** Keep client packages thin over the same report contract. Add SessionReport(session_id, authorized_repository_id, report_digest, head_or_snapshot, context_digest, report, freshness). Select repository identity through operator-granted workspace/service scope and look up reports by session/report ID, not an ambient global latest report. Preserve schema-1 full/limit_failure, side-aware locations, coverage and gaps. A local filesystem path is never a remote repository selector.

**Tech Stack:** Python stdlib MCP/unittest; native JavaScript VS Code extension using editor API; Node test runner in development only; versioned neutral plugin/skill manifests; remote protocol adapter outside kernel.

**Spec:** [E08 child specification](../specs/2026-10-03-e08-delivery-completion.md).

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

1. A global latest report must not leak a prior repository/session result (Task 1).
2. Malformed/oversized JSON or unsupported protocol versions fail within bounds (Tasks 1 and 4).
3. Unsaved edits/changed snapshots show stale or unavailable results, not current diagnostics (Task 2).
4. Malicious path/message/link text cannot navigate or execute outside the authorized workspace (Tasks 2–3).
5. Remote authentication/session/revocation cannot grant local filesystem or patch permissions (Task 4).

## File and interface map

- Task 1: modify `src/pullraptor/mcp_server.py`; create `src/pullraptor/mcp_sessions.py`; strict protocol and scoped state.
- Task 2: create `integrations/vscode/extension.js`, `integrations/vscode/test/extension.test.js`; modify `integrations/vscode/package.json`; native review commands, diagnostics and coverage.
- Task 3: create `integrations/assistant/plugin.json`, `integrations/terminal/plugin.json`, `integrations/install-matrix.json`; modify `skills/pullraptor-reviewer/SKILL.md`; versioned client installation and compatibility.
- Task 4: create `service/mcp_http.py`; modify `integrations/install-matrix.json`; remote protocol and identity boundary.

### Task 1: Bound stdio MCP and report/session identity

**Acceptance:** E08-A1.

**Files:** modify `src/pullraptor/mcp_server.py`; create `src/pullraptor/mcp_sessions.py`; test: `tests/test_mcp_sessions.py`.

**Interfaces:**
- Consumes: E02 accepted immutable local capture, kernel bounded codec/Report and operator-owned workspace grants.
- Produces: `get_session_report(session_id: str, report_digest: str, authorized_repository_id: str) -> SessionReport`; `handle_message(payload: bytes, session: MCPSession) -> bytes | None`; MCPSession(id, workspace_grants, negotiated_version, reports).

- [ ] **Step 1: Write the failing acceptance tests.** Add `test_cross_repo_session_report_denied`, `test_no_implicit_review_on_get`, `test_duplicate_keys_unknown_fields_rejected`, `test_oversized_message_bounded`, `test_eviction_explicit`, and `test_version_negotiation_strict`. A get request for repository B cannot return A's last report or silently analyze B; return report_not_found/denied.

Expected assertions for the stated adverse fixture:

```python
assert response_state == "report_not_found"
assert implicit_review_count == 0
assert repository_a_report_disclosed is False
```

- [ ] **Step 2: Run the focused suite and confirm a meaningful failure.** Run `PYTHONPATH=src python3.12 -m unittest tests.test_mcp_sessions tests.test_mcp_server -v`. Missing new interfaces may fail import initially; existing code must fail the new adverse assertion before correction.
- [ ] **Step 3: Implement the declared interfaces.** Require initialized version/session state, strict typed tool schemas and bounded UTF-8 line framing. Review returns a pinned report ID; findings/coverage/explain consume it. Preserve kernel exit/coverage and limit_failure; expose capability discovery only from admitted matrix. Keep workspace grant authority outside model parameters and use one shared review deadline.
- [ ] **Step 4: Run the same suite.** Require all named assertions to pass, including the successful fixture; retain raw outputs and exact input/tool identities.
- [ ] **Step 5: Commit the reviewed task on an allowed feature branch.** Stage only this task's files; use commit message `feat: bind MCP reports to bounded authorized sessions`. Do not commit to `main`.

### Task 2: Implement and package the native editor flow

**Acceptance:** E08-A2.

**Files:** create `integrations/vscode/extension.js`, `integrations/vscode/test/extension.test.js`; modify `integrations/vscode/package.json`; test: `integrations/vscode/test/extension.test.js`.

**Interfaces:**
- Consumes: Task 1 session/report contract and E07 installed trusted CLI; editor API and operator-selected executable.
- Produces: `activate(context)`/`deactivate()` extension entrypoints, `reviewWorkspace(mode)` command handler, read-only diagnostics/coverage presentation and installable versioned VSIX.

- [ ] **Step 1: Write the failing acceptance tests.** Add `stale_buffer_not_current`, `path_escape_not_opened`, `malicious_label_inert`, `deleted_side_location`, `partial_report_visible`, and `cancellation_preserves_incomplete`. Fixture: an unsaved buffer changes after capture; diagnostics carry stale state and no arbitrary URI/command is invoked.

Expected assertions for the stated adverse fixture:

```javascript
assert.equal(diagnosticsAreStale, true);
assert.equal(untrustedUriOpened, false);
```

- [ ] **Step 2: Run the focused suite and confirm a meaningful failure.** Run `node --test integrations/vscode/test/extension.test.js`. Missing new interfaces may fail import initially; existing code must fail the new adverse assertion before correction.
- [ ] **Step 3: Implement the declared interfaces.** Set manifest main to the authored entry point, invoke trusted binary with argument arrays and explicit environment, and present findings/receipts from immutable reports. Validate navigation against authorized path/side/revision; no raw HTML or command links. Preserve coverage when findings are absent. Package VSIX only after declared editor/runtime/license inventory; saved-file capture is required for unsaved edits initially.
- [ ] **Step 4: Run the same suite.** Require all named assertions to pass, including the successful fixture; retain raw outputs and exact input/tool identities. Run actual install/activate/review/staged/repeat/cancel/uninstall in pinned VS Code versions; Node mocks alone do not accept native delivery.
- [ ] **Step 5: Commit the reviewed task on an allowed feature branch.** Stage only this task's files; use commit message `feat: deliver native editor review and coverage`. Do not commit to `main`.

### Task 3: Package neutral assistant plugins and standalone skills

**Acceptance:** E08-A3.

**Files:** create `integrations/assistant/plugin.json`, `integrations/terminal/plugin.json`, `integrations/install-matrix.json`; modify `skills/pullraptor-reviewer/SKILL.md`; test: `tests/test_assistant_packages.py`.

**Interfaces:**
- Consumes: Task 1 local MCP contract and E07 release identities.
- Produces: versioned plugin bundles and standalone skill/MCP install manifests, each with client_role, client_version, session_kind, runtime_requirements, artifact_digest and admitted state.

- [ ] **Step 1: Write the failing acceptance tests.** Add `test_source_clone_not_required`, `test_plugin_cannot_grant_shell_or_merge`, `test_cloud_no_local_path_assumption`, `test_credentials_not_worker_environment`, and `test_uninstall_removes_connection`. Test terminal/IDE-hosted/cloud sessions separately; a missing runtime in cloud is unavailable rather than locally supported.

Expected assertions for the stated adverse fixture:

```python
assert cloud_without_runtime.state == "unavailable"
assert granted_arbitrary_shell is False
assert customer_clone_required is False
```

- [ ] **Step 2: Run the focused suite and confirm a meaningful failure.** Run `PYTHONPATH=src python3.12 -m unittest tests.test_assistant_packages -v`. Missing new interfaces may fail import initially; existing code must fail the new adverse assertion before correction.
- [ ] **Step 3: Implement the declared interfaces.** Select and pin actual client-specific schemas at compatibility admission while project copy keeps neutral roles; record tested client/version externally if its brand is excluded by project policy. Provide package install/update/revoke/uninstall flows, source-free artifact fetch verification and bounded read-only skill instructions. Standalone skill installation cannot claim a functioning engine without E07 runtime.
- [ ] **Step 4: Run the same suite.** Require all named assertions to pass, including the successful fixture; retain raw outputs and exact input/tool identities.
- [ ] **Step 5: Commit the reviewed task on an allowed feature branch.** Stage only this task's files; use commit message `feat: package tested assistant review integrations`. Do not commit to `main`.

### Task 4: Map authenticated remote MCP to service authority

**Acceptance:** E08-A4.

**Files:** create `service/mcp_http.py`; modify `integrations/install-matrix.json`; test: `tests/test_remote_mcp.py`.

**Interfaces:**
- Consumes: accepted E10 v1 API/Principal/capabilities and E11 authorization, plus Task 1 report/session semantics.
- Produces: `dispatch_remote(payload: bytes, principal: Principal, session_id: str) -> MCPResponse`; MCPResponse(status, body, protocol_version); review/report/capabilities/explain mapping only.

- [ ] **Step 1: Write the failing acceptance tests.** Add `test_remote_filesystem_path_denied`, `test_origin_and_protocol_version`, `test_cross_tenant_session_denied`, `test_revocation_on_report_access`, `test_disconnect_not_completion`, and `test_remote_cli_canonical_equal`. A remote repo_path is rejected before filesystem access; bad Origin and unsupported version fail before dispatch.

Expected assertions for the stated adverse fixture:

```python
assert filesystem_reads == 0
assert response.status == 400
assert disconnected_job_marked_complete is False
```

- [ ] **Step 2: Run the focused suite and confirm a meaningful failure.** Run `PYTHONPATH=src:. python3.12 -m unittest tests.test_remote_mcp -v`. Missing new interfaces may fail import initially; existing code must fail the new adverse assertion before correction.
- [ ] **Step 3: Implement the declared interfaces.** Pin remote 2025-06-18 Streamable HTTP independently from legacy stdio, validate Origin and authentication/session/version headers, bound requests and responses, and delegate only to authorized E10 repository IDs. Explicit cancellation calls service cancel; transport disconnection alone is not completion/cancellation evidence. Before remote activation, require accepted E10-A1/A2 and E11-A1/A2 for the consumed scope; E10-A4 first establishes the consumed service profile's CLI/API deployment evidence, then E08-A4 records CLI/API/MCP parity. Do not require full E08/E10/E11 acceptance to gather that scoped evidence, or expose an endpoint without its enforced authority/isolation boundary.
- [ ] **Step 4: Run the same suite.** Require all named assertions to pass, including the successful fixture; retain raw outputs and exact input/tool identities.
- [ ] **Step 5: Commit the reviewed task on an allowed feature branch.** Stage only this task's files; use commit message `feat: expose authorized remote review MCP`. Do not commit to `main`.

## Package acceptance and handoff

- [ ] Re-run this package's focused suites and the affected existing suites in the trusted development environment; reviewed-source execution uses only an accepted runner.
- [ ] Exercise the scoped install/connect → exact review → visible coverage → repeat after changes → revoke/uninstall flow where this package exposes a delivery surface.
- [ ] Record all E08-A1 through E08-A4 criteria, dependency/license inventory and actual resource measurements in `docs/acceptance/E08.md`.
- [ ] Obtain independent acceptance review. Until then retain the actual implementation state and acceptance pending in the master plan. Accepted subsets do not mark the broader package complete.
