# Beta 0.1.0b2 maintenance entry criteria

Human label **beta 0.1.x** patch releases after the first accepted artifact (`0.1.0b1`). Do **not** tag `0.1.0b2` proactively.

## Required triggers (any one opens the lane)

1. **Customer- or CI-blocking defect** on the published wheel that cannot be resolved by documentation alone.
2. **Coordinator-authorized doc or packaging fix** that must ship as an immutable GitHub Release asset (not only `main` docs).

## Preconditions before tag

| Gate | Requirement |
|---|---|
| Prior artifact | `0.1.0b1` remains the accepted rollback baseline ([beta-0.1-release-manifest.json](beta-0.1-release-manifest.json)) |
| BR-18 | Execute update/interrupted-update/rollback rehearsal from [release-tasks.json](../release-tasks.json) **before** advertising update or rollback support |
| Build | Rebuild wheel with [release/build.py](../../release/build.py) at merge OID (`git archive`, Python 3.12, `SOURCE_DATE_EPOCH=0`) |
| Evidence | Refresh manifest, dual-build receipts, and install smoke (CI + BR-17-style download check) |
| Scope | No widening of beta capability gates without new acceptance; `pullraptor-publish` stays refused for customers until E02 gates authorize |

## Defect queue (maintainer-owned)

Record concrete issues here before cutting `0.1.0b2`. Empty queue means **no release**.

| ID | Summary | Severity | Fix PR | Status |
|---|---|---|---|---|
| — | *none filed* | — | — | — |

## Exit

- New tag `v0.1.0b2` with updated [beta-0.1-notes.md](beta-0.1-notes.md) or successor patch notes.
- Manifest `proposed_package_version` / artifacts updated; BR-18 evidence attached to acceptance dossier.
