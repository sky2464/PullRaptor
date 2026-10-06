# Release acceptance record: beta 0.1.x

Date: 2026-10-06. **Readiness:** ready for release (beta subset). **Publication:** pending BR-15 authorization on this commit.

## Frozen candidate identity

| Field | Value |
|---|---|
| Source revision | `097e9ae6fdad6ec5c10934e26f8e0fa56c8eaf4c` |
| Wheel SHA-256 | `d44d6da0e6fc667a26260896cd5f4d82c35b59f8126e65ce38d92d9a8e97be24` |
| Wheel file | `pullraptor-0.1.0b1-py3-none-any.whl` |
| Scope | `docs/releases/beta-0.1-scope.json` |
| Manifest | `docs/releases/beta-0.1-release-manifest.json` |

## Independent decisions

| Package | Reviewer | Decision |
|---|---|---|
| E01 beta subset | sme_reviewer_agent_e01_2026_10_06 | **accepted** |
| E07 wheel subset | sme_reviewer_agent_e07_2026_10_06 | **accepted** |

## Authorization states

- `ready_for_release`: **true** (BR-01–13 beta subset)
- `publication_authorized`: **true** ([publication-decision.md](../../releases/beta-0.1-publication-decision.md) GO 2026-10-06)
- `released_verified`: **true** ([post-publication.md](../../releases/beta-0.1-post-publication.md))

## Exclusions visible

All `conditional_requires` capabilities in `docs/releases/beta-0.1-capability-gates.json` excluded from beta claims with containment evidence.
