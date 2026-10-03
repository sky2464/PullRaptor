# E08: Editor, plugin and local/remote MCP delivery acceptance specification

Date: 2026-10-03. Status: proposed child design; acceptance pending.

**Parent:** [Master plan](../../../Master-Plan.md), [product specification](2026-10-03-pullraptor-design.md), [mathematical core](../../mathematical-core.md), [security architecture](../../security-architecture.md), [evaluation](../../evaluation.md), and [execution contract](../../planning-contract.md).

## Outcome and scope

Complete bounded stdio MCP, a functioning packaged VS Code extension, neutral AI-editor/terminal-assistant plugin bundles and standalone skills, plus authenticated remote MCP. Current code supports a stdio prototype and manifest/skill subset; no extension implementation or plugin release was observed. This child governs full-roadmap acceptance beyond the earlier narrow E08 spec.

## Dependencies and delivery boundary

E01/E02 local snapshot/report and E07 artifact acceptance for local delivery; optional explanation uses E03. Remote mode requires accepted E10 API and E11 identity/isolation essentials. E06 is required only if patch apply/validation is separately exposed; initial editor/MCP actions are review/read/explain with no publication or application command.

## Architecture and records

Keep client packages thin over the same report contract. Add SessionReport(session_id, authorized_repository_id, report_digest, head_or_snapshot, context_digest, report, freshness). Select repository identity through operator-granted workspace/service scope and look up reports by session/report ID, not an ambient global latest report. Preserve schema-1 full/limit_failure, side-aware locations, coverage and gaps. A local filesystem path is never a remote repository selector.

## Resource, dependency and compatibility budget

MCP request ≤1,048,576 bytes/depth 64/10,000 items; response ≤8,388,608 bytes with explicit protocol failure when a report cannot fit. At most 2 active reviews/session and 10 retained reports/64 MiB, eviction explicit. Extension/plugin authored bundle ≤5 MiB each excluding Python/Git, idle RSS target ≤128 MiB and activation target ≤2 seconds. Proposed Python adapter completion ≤600 lines and editor/plugin authored code ≤800 lines. Local stdio initially pins 2024-11-05; proposed remote Streamable HTTP pins 2025-06-18 separately and does not claim latest compatibility. Pin actual client/editor versions and build/runtime/license inventories before admission.

## Acceptance criteria

Each criterion is required for the named scope. Cases are future checks; none was run in this planning change.

| ID | Required behavior and evidence |
|---|---|
| E08-A1 | Stdio protocol bounds/version/notification/error fixtures and cross-repo/session/stale/eviction checks preserve scope and full/limit-failure semantics; no hidden review or unauthorized state reuse. |
| E08-A2 | An actual installed VSIX runs all documented commands and preserves exact locations, partial/stale/cancel states, safe rendering and no unauthorized writes; activation/RSS/bundle size are measured per editor version. |
| E08-A3 | Every claimed client/version/session has actual install/connect/review/repeat/revoke/uninstall evidence and report parity; unsupported cloud/runtime/session combinations remain explicit. Package/skill instructions grant no extra execution or publication authority. |
| E08-A4 | Authenticated remote MCP preserves tenant/repository/job/report identities, revocation, bounded protocol and Origin checks with no server-path selection; actual supported-client flow and canonical CLI/API/MCP report parity are recorded. |

## Failure and claim policy

Version mismatch, rejected workspace, stale report, evicted session, partial review and transport failure are distinct visible states. Preserve requested scope; coverage is based on receipts, not invented ratios of lines inspected. Unsaved buffers remain unsupported until a bounded immutable buffer-manifest contract is accepted; ask the user to save and recapture rather than silently scanning mutable text. No client instruction can promote authority or merge.

**Implementation plan:** [E08 tasks](../plans/2026-10-03-e08-delivery-completion.md). Save acceptance in `docs/acceptance/E08.md`; use the execution contract's evidence fields and independent acceptance decision.
