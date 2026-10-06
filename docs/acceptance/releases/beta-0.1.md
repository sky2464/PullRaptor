# Release acceptance record: beta 0.1.x (candidate)

Date: 2026-10-05. **Readiness:** not ready for release. **Publication:** not authorized.

## Frozen candidate identity

| Field | Value |
|---|---|
| Source revision | `f95fd1b33af5b040fc3fa4ea2e1f1b3604b8fa74` (rebuild at merge commit after PR lands) |
| Wheel SHA-256 | `b1d8df90023868ba666408318d96a1075720082faf6a86c51e6af42ecc05f700` (git archive + SOURCE_DATE_EPOCH build; prior `6f1b9d3` receipt stale) |
| Scope | `docs/releases/beta-0.1-scope.json` |
| Manifest | `docs/releases/beta-0.1-release-manifest.json` |

## Independent decisions

| Package | Reviewer | Decision |
|---|---|---|
| E01 beta subset | unassigned | pending (`docs/acceptance/artifacts/E01/independent-review.md`) |
| E07 wheel subset | unassigned | pending (`docs/acceptance/artifacts/E07/independent-review.md`) |

## Authorization states

- `ready_for_release`: **false** (BR-07/13 blocked; recovery rehearsal not_run; independent benchmark acceptance pending)
- `publication_authorized`: **false** (BR-15 not executed)
- `released_verified`: **false** (BR-17 not applicable)

## Exclusions visible

All `conditional_requires` capabilities in `docs/releases/beta-0.1-capability-gates.json` are excluded from beta claims with containment evidence for publisher/MCP/local snapshot CLI flags.
