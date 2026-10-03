# E06-D1: Exact text edit and private tree backend

Date: 2026-10-03. Status: coordinator interface decision (construction prerequisite for E06-T1).

## PathEdit wire semantics (schema version `e06-path-edit/1`)

| Field | Type | Rule |
|---|---|---|
| `path` | string | Repository-relative POSIX path; no leading `/`, no `..` segments, no encoded separators (`%2f`, backslashes). |
| `old_blob` | string | 40-char lowercase hex Git blob OID for replacement; literal sentinel `0000000000000000000000000000000000000000` means addition (path must be absent on head). |
| `old_mode` | string | Git tree entry mode for replacement (`100644` regular file only for additions); must match head entry for replacements. |
| `new_bytes` | string (UTF-8) | Full replacement file content after edit; must not be empty for replacements (deletions are unsupported). |

Unsupported in v1: hunks/partial edits, renames, deletions, mode changes, executable bit (`100755`), symlinks (`120000`), submodules (`160000`).

## Trusted scope

- `PatchProposal.allowed_paths` is proposal metadata only.
- Application and P0 checks use `trusted_allowed_paths` supplied by coordinator-owned policy; intersection is not sufficient—only trusted paths may be edited.

## Protected paths

Paths matching any of these prefixes are denied regardless of proposal grants:

- `.git/`
- `.github/workflows/`

## Tree materialization

1. **Synthetic fixture backend (default for unit tests):** in-memory blob store keyed by OID; result trees use OIDs prefixed `synthetic-tree:` and are never valid Git provenance.
2. **Private Git scratch backend (optional integration):** `hash-object` / `mktree` in a temporary directory with `_git_env()` / `_safe_git_args()` from `git_snapshot.py`; does not read or write the developer index, refs, or working tree.

## Stage dependency (Task 1 scope)

- **P0** validates head OID, per-edit preconditions, path grants, and protected-path rules.
- **P1** applies exact full-file replacements/additions to an immutable result tree when P0 passes.
- P2–P4 are out of scope for Task 1; callers must not treat Task 1 output as full validation receipt.
