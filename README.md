# PullRaptor

PullRaptor is an offline, local-first pull request reviewer built around the difference between two immutable revisions and the evidence needed to explain that difference.

Its promise is simple: **show what changed, what may break, why a finding deserves attention, and what remains unexamined.**

## Implemented Architecture (E01)

- Small deterministic Python 3.12+ kernel with zero third-party runtime packages.
- Git-backed immutable snapshots, readable summaries, canonical JSON, and SARIF 2.1.0 output.
- Generic diff review for any text language; semantic pattern review for Python.
- Three advisory factual rules (PY001 mutable default argument mutation, PY002 bare exception handler, PY003 subprocess with shell=True).
- Coordinator-owned review contract, independent coverage receipts, and fresh run-local import resolution.
- Private, owner-checked parser cache with clean/incremental canonical equivalence.
- Bounded decoding, streaming process controls, and injection-safe rendering.

## Usage

Run PullRaptor directly via Python 3.12:

# Review uncommitted working tree changes against HEAD
python3.12 -m pullraptor --workdir

# Review staged index changes against HEAD
python3.12 -m pullraptor --staged

# Markdown review of current HEAD against main
python3.12 -m pullraptor --base main --head HEAD

# Machine-readable canonical JSON
python3.12 -m pullraptor --base main --head HEAD --format json --no-cache

# SARIF 2.1.0 report
python3.12 -m pullraptor --base main --head HEAD --format sarif

# Explicit diff-only profile (bypasses semantic analysis)
python3.12 -m pullraptor --base main --head HEAD --profile diff

# Publish review report to GitHub PR with drift validation and comment idempotency
pullraptor-publish --report report.json --repo-slug owner/repo --pr 42
```

### Running via Docker

Build and run the isolated, pinned `python:3.12-slim` container:

```bash
docker build -t pullraptor .

# Run test suite
docker run --rm pullraptor

# Run review on a mounted repository
docker run --rm -v "$(pwd):/repo" pullraptor python -m pullraptor --repo /repo --base main --head HEAD
```

### Exit Codes

- `0`: Requested analysis complete with no blocking findings
- `1`: Complete with a configured blocker
- `2`: Required analysis incomplete or unavailable (e.g. unresolved imports, parse failures, or resource limits)
- `3`: Tool, configuration, or input failure

## Architecture Documentation

| Document | Purpose |
|---|---|
| [Master plan](Master-Plan.md) | Release order, scope, gates, and decisions |
| [Product and architecture specification](docs/superpowers/specs/2026-10-03-pullraptor-design.md) | User flows, interfaces, runtime choice, trust boundaries |
| [Mathematical core](docs/mathematical-core.md) | Algorithms, equations, assumptions, and counterexamples |
| [Capability review](docs/research/2026-10-03-capability-review.md) | Workflow capabilities and acceptance criteria |
| [Security and architecture contract](docs/security-architecture.md) | Scope authority, process/cache boundaries, rendering and publication controls |
| [Independent review decisions](docs/reviews/2026-10-03-security-architecture.md) | Adopted improvements, evidence, tradeoffs and remaining limits |
| [Evaluation contract](docs/evaluation.md) | Accuracy, coverage, resource, and regression gates |
| [Review kernel plan](docs/superpowers/plans/2026-10-03-review-kernel.md) | Implementation tasks and verification steps for E01 |
