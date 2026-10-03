# E04 worker process contract

Date: 2026-10-03. Status: construction reference for E04-D0/E04-T1; acceptance pending.

## Transport

- Coordinator calls `run_bounded` with `input_bytes` set to one strict JSON request and `max_input_bytes` capped at `RecordLimits.max_payload_bytes` (8,388,608).
- Stdin is closed after the request bytes are written. Stdout and stderr are drained concurrently under the same review `Deadline` and per-invocation `ProcessBounds`.
- Default Git subprocess calls keep `input_bytes=None` (stdin `DEVNULL`).

## Request (schema version 1)

Protocol key: `pullraptor_language_worker_v1`.

Fields: `contract_digest`, `scope_keys`, `language`, `grammar_digest`, `capability`, `source_blobs` (path plus base64-encoded bytes). Source bytes are untrusted data; workers must not import or execute them.

## Response

Same protocol key. Fields mirror `LanguageResult`: `contract_digest`, `completed_keys`, `content_facts`, `unsupported`, `producer_digest`. The coordinator validates receipts against requested scope independently.

## Registry authority

`LanguageRegistryEntry` pins `executable_argv`, `executable_digest`, `grammar_digest`, `allowed_environment`, and neutral `worker_cwd`. Dispatch refuses unknown language/capability pairs, digest mismatches, and oversize requests before launch.

## Development fixtures

`tests/fixtures/languages/protocol/inert_worker.py` is an inert fixture for protocol dispatch tests only. It is not a language parser and does not admit any live capability.
