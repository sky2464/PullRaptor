# Release acceptance record: beta 0.1.x (candidate)

Date: 2026-10-05. **Readiness:** not ready for release. **Publication:** not authorized.

## Frozen candidate identity

| Field | Value |
|---|---|
| Source revision | `6f1b9d370f6332e88675d3bf2b681713b6840e44` |
| Wheel SHA-256 | `397308789ed691d784fd0fe5ec003204a37c7e4983d6a14834edf91f2d6fc91e` |
| Scope | `docs/releases/beta-0.1-scope.json` |
| Manifest | `docs/releases/beta-0.1-release-manifest.json` |

## Independent decisions

| Package | Reviewer | Decision |
|---|---|---|
| E01 beta subset | unassigned | pending (`docs/acceptance/artifacts/E01/independent-review.md`) |
| E07 wheel subset | unassigned | pending (`docs/acceptance/artifacts/E07/independent-review.md`) |

## Authorization states

- `ready_for_release`: **false** (BR-07/13 blocked; recovery rehearsal not_run; benchmarks incomplete)
- `publication_authorized`: **false** (BR-15 not executed)
- `released_verified`: **false** (BR-17 not applicable)

## Exclusions visible

All `conditional_requires` capabilities in `docs/releases/beta-0.1-capability-gates.json` are excluded from beta claims with containment evidence for publisher/MCP/local snapshot CLI flags.
