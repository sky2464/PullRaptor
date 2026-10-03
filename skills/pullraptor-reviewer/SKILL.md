---
name: pullraptor-reviewer
description: Run deterministic offline code reviews, inspect structural findings, and check verification coverage receipts on Git repositories.
---

# PullRaptor Reviewer Skill

This skill guides coding assistants and automated agents on executing reviews, inspecting findings, and checking coverage using PullRaptor.

## When to Use

Use this skill when:
- Reviewing uncommitted working tree or staged changes before commit/push.
- Inspecting structural AST diffs and code obligations for Python code.
- Verifying whether all changed lines have coverage receipts and zero unexpected omissions.
- Explaining detected advisory findings and remediation patterns.

## Available Invocations

### 1. Via CLI

```bash
# Review uncommitted working tree changes against HEAD
pullraptor --workdir

# Review staged index changes against HEAD
pullraptor --staged

# Review a specific commit or revision range
pullraptor --base HEAD~1 --head HEAD

# Output formatted JSON or SARIF for tooling
pullraptor --staged --format json
pullraptor --workdir --format sarif
```

### 2. Via Model Context Protocol (MCP)

When PullRaptor MCP server is active (`pullraptor mcp` or `pullraptor-mcp`), use the following tools:

- `pullraptor_review`:
  - `workdir: true` — inspect uncommitted files.
  - `staged: true` — inspect staged git index.
  - `base: "HEAD~1"`, `head: "HEAD"` — inspect specific revisions.
- `pullraptor_get_findings`:
  - Query filtered diagnostic findings with exact file paths and line ranges.
- `pullraptor_get_coverage`:
  - Retrieve verified coverage receipts, analyzed entries, and skipped file reasons.
- `pullraptor_explain_finding`:
  - Pass `rule_id` (e.g., `PY001`, `PY002`, `PY003`) to obtain full rationale and safe remediation instructions.

## Guiding Principles

1. **Deterministic Authority**: The deterministic review kernel alone defines verified findings and coverage. Explanations or advice from language models are advisory proposals and cannot dismiss findings or authorize code merge.
2. **Path Containment**: Target repositories must be valid Git roots. Arbitrary file path traversals outside the repository root are strictly disallowed.
3. **No Execution of Reviewed Code**: Analysis parses code syntactically and structurally; target repository scripts are never executed during review.
