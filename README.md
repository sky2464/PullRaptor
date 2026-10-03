# PullRaptor

PullRaptor is a proposed local-first pull request reviewer built around the difference between two revisions and the evidence needed to explain that difference.

Its intended promise is simple: **show what changed, what may break, why a finding deserves attention, and what remains unexamined.**

This repository currently contains research-derived design and implementation plans. There is no working reviewer, installer, integration, or measured performance result yet.

## Proposed direction

- A small deterministic Python kernel with zero third-party runtime packages.
- Git-backed immutable snapshots, readable summaries, JSON and SARIF output.
- Generic diff review for any text language; deeper analysis only for explicitly supported language capabilities.
- Optional bounded AI reasoning, conversation, and patch proposals.
- Evidence tied to exact revisions, explicit uncertainty, and reproducible incremental analysis.
- CLI first, GitHub CI next, broader integrations through small adapters.

## Read the plan

| Document | Purpose |
|---|---|
| [Master plan](Master-Plan.md) | Release order, scope, gates, and decisions |
| [Product and architecture specification](docs/superpowers/specs/2026-10-03-pullraptor-design.md) | User flows, interfaces, runtime choice, trust boundaries |
| [Mathematical core](docs/mathematical-core.md) | Algorithms, equations, assumptions, and counterexamples |
| [Capability review](docs/research/2026-10-03-capability-review.md) | Research findings translated into 30 independently testable capabilities |
| [Evaluation contract](docs/evaluation.md) | Accuracy, coverage, resource, and regression gates |
| [First implementation plan](docs/superpowers/plans/2026-10-03-review-kernel.md) | Reviewable tasks for the initial offline kernel |

Product documents use PullRaptor's own terminology and contain no competing product names. The named market comparison and its official source links remain in the originating conversation.

## Planned usage

These commands describe the intended interface; they do not work yet.

```text
pullraptor review --base main --head HEAD --format markdown
pullraptor review --base main --head HEAD --format json --no-cache
pullraptor review --base main --head HEAD --profile diff --format sarif
```

The default structural profile initially targets Python. The explicit diff profile offers summaries for other text languages and says that semantic correctness was not evaluated. AI is disabled by default. No mode equates an empty findings list with proof of safety.
