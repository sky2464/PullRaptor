# E02 local consumer parity (construction evidence)

Date: 2026-10-03. Card: `E02-T1-CONSUMERS`.

CLI and MCP both route staged/workdir reviews through `resolve_local_review_refs` → `capture_local`. The CLI exposes `--include-untracked` (default false); MCP uses the `include_untracked` tool argument with the same default.

Automated checks: `tests/test_working_tree.py` (`test_cli_untracked_*`, `test_mcp_local_snapshot_*`, `test_local_partial_receipt_survives_adapter`). Product acceptance (`E02-A1`) remains pending independent evidence.
