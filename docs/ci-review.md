# Hardened GitHub review template

The declarative contract lives at `integrations/github/review.yml`. It separates:

- **Analyze job:** installs a pinned trusted artifact outside PR head content, acquires head bytes in `pr-head/` with `persist-credentials: false`, passes PR title/body as plain environment data, probes disposable isolation through `pullraptor.publication_trust probe-isolation`, and refuses the hostile profile when required controls are not proven.
- **Publish job:** uses a separate credential (`PULLRAPTOR_PUBLISH_TOKEN`), downloads only bounded report artifacts, validates `pullraptor-receipt.json` against the current workflow run (replay denied), checks out only the trusted publisher artifact (never PR head), and never restores analysis caches.

Forked PRs should run analysis only; publication remains disabled when `head.repo` differs from the base repository.

## Isolation probe environment

Coordinator-owned runners must export all of the following before `probe-isolation` succeeds:

| Variable | Required value |
|---|---|
| `PULLRAPTOR_ISOLATION_EGRESS_DENIED` | `true` / `1` / `enforced` |
| `PULLRAPTOR_ISOLATION_SOURCE_READONLY` | `true` / `1` / `enforced` |
| `PULLRAPTOR_ISOLATION_PROCESS` | `true` / `1` / `enforced` |

The analyze job must not receive `PULLRAPTOR_PUBLISH_TOKEN` or other publisher credentials. When any control is missing, admission is `unavailable` and the analyze job exits non-zero (fail-closed hostile profile).

## Development repository CI policy

PullRaptor's own `.github/workflows/ci.yml` is compared to the merge-base revision on every pull request. Head changes cannot elevate `permissions`, remove required verification markers, or drop unit-test discovery. Enforcement uses `python -m pullraptor.publication_trust verify-dev-ci`.

Activating the customer review template in a repository requires coordinator authorization and E02-A4 acceptance evidence.
