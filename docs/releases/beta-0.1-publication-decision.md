# Beta 0.1.0b1 publication decision (BR-15)

Date: 2026-10-06. **Maintainer:** `human_coordinator`.

## Candidate presented

| Field | Value |
|---|---|
| Source OID | `097e9ae6fdad6ec5c10934e26f8e0fa56c8eaf4c` |
| Tag | `v0.1.0b1` |
| Wheel | `pullraptor-0.1.0b1-py3-none-any.whl` |
| SHA-256 | `d44d6da0e6fc667a26260896cd5f4d82c35b59f8126e65ce38d92d9a8e97be24` |
| Channel | GitHub Release on `sky2464/PullRaptor` |
| Scope | [beta-0.1-scope.json](beta-0.1-scope.json) |
| Notes | [beta-0.1-notes.md](beta-0.1-notes.md) |

## Decision

- **Go / no-go:** **GO**
- **Publication operator:** `human_coordinator`
- **Credential boundary:** GitHub `gh` release identity only; no tokens passed to review workers

## Authorization

Publication of the exact wheel bytes listed above is **authorized**. Do not publish if digest or source OID changes without repeating BR-07/BR-13 and this decision.
