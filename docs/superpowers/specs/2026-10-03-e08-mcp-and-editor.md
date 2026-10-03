# Specification: Milestone E08 — Editor & Agent Integration (MCP Server & Tools)

**Document ID:** `docs/superpowers/specs/2026-10-03-e08-mcp-and-editor.md`  
**Milestone:** E08  
**Status:** Complete  
**Date:** 2026-10-03  

---

## 1. Objective & Scope

Milestone E08 provides standard integration protocols allowing code editors, IDEs, and autonomous terminal assistants to invoke PullRaptor reviews and consume structured findings, coverage receipts, and explanations.

Specifically, this milestone delivers:
1. **Model Context Protocol (MCP) Server**: A standard stdio-based JSON-RPC 2.0 MCP server implemented using standard-library Python (`sys.stdin`/`sys.stdout`), requiring zero third-party packages or external daemon dependencies.
2. **Exposed MCP Tools & Resources**:
   - `pullraptor_review`: Execute deterministic review against committed revisions, staged index, or uncommitted working tree snapshots.
   - `pullraptor_get_findings`: Query and filter diagnostic findings by file path, severity, and rule ID.
   - `pullraptor_get_coverage`: Retrieve verification scope, receipts, and ratio of analyzed lines vs skipped files.
   - `pullraptor_explain_finding`: Retrieve deterministic rule explanations or optional advisory model explanations (if configured).
   - Resources: `pullraptor://report/latest` and `pullraptor://coverage/summary`.
3. **Editor & Assistant Packages**:
   - Agent skill specification (`skills/pullraptor-reviewer/SKILL.md`) describing how assistants invoke PullRaptor via CLI and MCP.
   - Extension manifest template (`integrations/vscode/package.json`) mapping editor commands to PullRaptor CLI/MCP entrypoints.
4. **Safety & Containment Invariants**:
   - Path containment: All target repository paths are resolved and validated against authorized directory boundaries. Path traversal attempts (`../`) outside the repository root are rejected.
   - Read-only review authority: MCP tools do not execute arbitrary shell commands, do not modify checked-out working trees, and cannot authorize automatic merge.
   - Zero external runtime dependencies: Built strictly with Python standard library.

---

## 2. MCP JSON-RPC 2.0 Wire Protocol

The MCP adapter adheres to the Model Context Protocol 2024-11-05 standard over stdio newline-delimited JSON-RPC messages.

### 2.1 Initialization
- Client sends:
  ```json
  {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "clientInfo": {"name": "client", "version": "1.0.0"}}}
  ```
- Server responds:
  ```json
  {
    "jsonrpc": "2.0",
    "id": 1,
    "result": {
      "protocolVersion": "2024-11-05",
      "capabilities": {
        "tools": {},
        "resources": {}
      },
      "serverInfo": {
        "name": "pullraptor-mcp",
        "version": "0.3.0"
      }
    }
  }
  ```
- Client sends: `notifications/initialized`

### 2.2 Tool Listing (`tools/list`)
Returns schema definitions for:
- `pullraptor_review`
- `pullraptor_get_findings`
- `pullraptor_get_coverage`
- `pullraptor_explain_finding`

### 2.3 Tool Invocations (`tools/call`)
Each invocation dispatches to the corresponding safe internal function, capturing exceptions into standard MCP tool response envelopes:
```json
{
  "content": [
    {
      "type": "text",
      "text": "<result payload or summary>"
    }
  ],
  "isError": false
}
```

---

## 3. Security & Safety Contract

1. **Path Boundary**: Any `repo_path` parameter is canonicalized via `os.path.realpath`. Traversal beyond the target workspace root raises an immediate path authorization error.
2. **Immutable Revisions & Isolated Snapshots**: Staged and uncommitted reviews use the E02 snapshot mechanism, ensuring ephemeral trees are isolated and never mutate on-disk workdir files.
3. **No Ambient Privileges**: The MCP server passes strict, sanitized environments without granting credential access or network capabilities to the review kernel.
4. **Zero Competitor Reference Policy**: No proprietary product names or vendor domains are present in any schemas, tool descriptions, or prompts.
