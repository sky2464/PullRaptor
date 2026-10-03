# E05 Python statement IR (schema 1)

Date: 2026-10-03. Status: construction artifact for E05-D1; acceptance pending.

## Purpose

Provide occurrence-free, ordered statement IR so bounded CFG construction and hazard/authorization analyses do not reconstruct control flow from lexical `ContentFacts`. The IR is immutable, versioned, and cacheable without path, snapshot, or tenant identity.

## Records

| Record | Role |
|--------|------|
| `RelativeSpan` | UTF-8 byte offsets and 1-based line/column coordinates relative to the reviewed blob |
| `IROperation` | Tagged operation (`name_assign`, `call`, `if`, …); constant kinds only—no persisted secret literals |
| `IRNode` | Local `node_id`, operation, span, explicit `Successor` edges |
| `FunctionIR` | One function body: parameters, bindings, ordered nodes, completeness flag |
| `StatementIR` | Blob digest, `schema_version` (`1`), `producer_id`, `runtime_version`, functions, module boundaries |
| `BoundStatementIR` | `StatementIR` plus coordinator-validated `contract_digest`, `snapshot`, `path`, `side` |

Cache keys hash `blob_digest`, schema, producer, and runtime (`statement_ir_cache_key`).

## Supported lowering subset

Straight-line code, `if`, `while`/`for` with `break`/`continue`/`else`, `return`/`raise`, resolved calls, and value-preserving unary/binary ops on names. `try`/`with`/async/comprehensions/dynamic dispatch emit `BoundaryRecord` entries and mark the function or module incomplete. Exception successors are not invented.

## Builtin `input` binding

Lowering records `BindingRecord` entries for parameters, locals, and imports. Names that shadow built-in `input` set `shadows_builtin_input`. Ambiguous or unresolved callees use `callee_resolution="unknown"`.

## Handcrafted fixtures

Immutable JSON fixtures under `tests/fixtures/security/flow/` exercise branch ordering, loop control, and round-trip serialization without a taint engine. JSON shape is described by `tests/fixtures/security/flow/ir-schema.json`.

## Non-goals (this milestone)

No `build_cfg`, hazard worklist, or `SecurityModel` transfer engine. Production PYSEC001 integration consumes `BoundStatementIR` in a later E05-T1 task.
