# Hardened GitHub review template

The declarative contract lives at `integrations/github/review.yml`. It separates:

- **Analyze job:** installs a pinned trusted artifact outside PR head content, passes PR title/body as plain environment data, does not persist checkout credentials, and records egress isolation as `unavailable` when OS enforcement cannot be proven in-template.
- **Publish job:** uses a separate credential (`PULLRAPTOR_PUBLISH_TOKEN`), downloads only bounded report artifacts, and never checks out the PR head for publication.

Forked PRs should run analysis only; publication remains disabled when `head.repo` differs from the base repository.

This file documents the template; activating it in a repository requires coordinator authorization and E02-A4 acceptance evidence.
