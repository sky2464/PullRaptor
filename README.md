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

```bash
# Markdown review of current HEAD against main
python3.12 -m pullraptor --base main --head HEAD

# Machine-readable canonical JSON
python3.12 -m pullraptor --base main --head HEAD --format json --no-cache

# SARIF 2.1.0 report
python3.12 -m pullraptor --base main --head HEAD --format sarif

# Explicit diff-only profile (bypasses semantic analysis)
python3.12 -m pullraptor --base main --head HEAD --profile diff
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
