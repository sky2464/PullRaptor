# Implementation Plan: Milestone E08 — Editor & Agent Integration (MCP Server & Tools)

**Document ID:** `docs/superpowers/plans/2026-10-03-e08-mcp-and-editor.md`  
**Milestone:** E08  
**Status:** Complete  
**Date:** 2026-10-03  

---

## 1. Modules to Introduce / Modify

1. **`src/pullraptor/mcp_server.py`** (New module, ~250 lines):
   - JSON-RPC 2.0 message loop reading from `sys.stdin` and writing to `sys.stdout`.
   - Handlers for `initialize`, `notifications/initialized`, `ping`.
   - Handlers for `tools/list` and `tools/call`.
   - Handlers for `resources/list` and `resources/read`.
   - Tool dispatch:
     - `pullraptor_review`: invokes `ReviewOrchestrator` or CLI kernel and caches latest report in memory.
     - `pullraptor_get_findings`: filters cached or fresh report findings.
     - `pullraptor_get_coverage`: formats receipts and coverage metrics.
     - `pullraptor_explain_finding`: provides rule rationale or calls `query_ai_provider` if configured.
   - Safe path sanitization with `os.path.realpath`.

2. **`src/pullraptor/__main__.py`** (Update existing):
   - Add `mcp` sub-command / flag: `pullraptor --mcp` or `pullraptor mcp` to start stdio MCP server.

3. **`skills/pullraptor-reviewer/SKILL.md`** (New documentation/skill):
   - Instructions and usage patterns for autonomous terminal assistants and AI pair programmers to run deterministic reviews.

4. **`integrations/vscode/package.json`** (New integration manifest):
   - Extension manifest defining commands, settings, and language diagnostic provider mappings.

5. **`tests/test_mcp_server.py`** (New test suite, ~150 lines):
   - Test JSON-RPC framing and initialization handshake.
   - Test tool listing output schema.
   - Test tool dispatch for review, findings, and coverage.
   - Test path traversal boundary rejection.
   - Test graceful error handling on malformed JSON-RPC payloads.

---

## 2. Invariant Checks

- Zero third-party runtime package dependencies.
- Zero competitor brand names or domains.
- All tests passing (existing 109 + new tests).
- Clean repository on feature branch `feat/e08-mcp-and-editor-integration`.
