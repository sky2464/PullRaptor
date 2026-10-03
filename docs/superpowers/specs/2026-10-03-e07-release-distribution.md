# E07: Packaged release, provenance and offline installation specification

Date: 2026-10-03. Status: proposed child design; acceptance pending.

**Parent:** [Master plan](../../../Master-Plan.md), [product specification](2026-10-03-pullraptor-design.md), [mathematical core](../../mathematical-core.md), [security architecture](../../security-architecture.md), [evaluation](../../evaluation.md), and [execution contract](../../planning-contract.md).

## Outcome and scope

Finish wheel/source archive/container distribution for the existing CLI/publisher/MCP entry points. Source checkout is a development path, not a customer install requirement. Release provenance, runtime/license inventory, offline install, uninstall/update/rollback and canonical artifact equivalence belong here. Existing pyproject and Dockerfile are packaging inputs, not evidence of published accepted releases.

## Dependencies and delivery boundary

E01 acceptance precedes release claims. Supply a pinned trusted artifact to E02 CI and E08 integrations. External publication is a separate authorized release action after acceptance; this plan does not publish a registry package or container.

## Architecture and records

Build only from an exact reviewed revision in a trusted build environment. Add ReleaseManifest(version, source_revision, artifacts, runtime_matrix, dependency_inventory, provenance_ref), ArtifactIdentity(kind, digest, size, entrypoints), and InstallReceipt(platform, runtime, artifact_digest, operation, result). Compare logical report output from source and installed artifacts; timestamps/build metadata are outside canonical analysis.

## Resource, dependency and compatibility budget

Core installed code/artifact ≤5 MiB excluding Python/Git; optional extras ≤100 MiB, with exceptions recorded by scope/cost decision. Proposed compressed reviewer container ≤256 MiB, separately inventoried. Initial support: Python 3.12.x on Linux x86_64 and macOS arm64, Linux x86_64 container; other combinations remain unaccepted. Proposed install startup ≤2 seconds and idle RSS ≤64 MiB on the documented runner. Setuptools/wheel tooling is build-only, exact versions/hashes/license inventory required. Pin container base by digest, not only a mutable `python:3.12-slim` tag.

## Acceptance criteria

Each criterion is required for the named scope. Cases are future checks; none was run in this planning change.

| ID | Required behavior and evidence |
|---|---|
| E07-A1 | Metadata, entry points and image defaults match declared profiles; runtime/license inventory is complete and no global trust wildcard or mandatory third-party kernel package remains. |
| E07-A2 | Tampered/misassociated artifacts are rejected; independently derived build/source origins and all build/runtime dependencies are verifiable. Two build outputs and reproducibility limits are recorded. |
| E07-A3 | Every claimed platform/profile installs without cloning, proves offline behavior and completed canonical equivalence, and passes uninstall/interrupted-update/rollback checks with measured footprint and explicit unsupported matrix rows. |

## Failure and claim policy

Invalid/missing provenance prevents release admission. Unsupported runtimes/platforms fail with explicit requirements; no silent downgrade or auto-install. Interrupted installation retains the previous accepted version or a recoverable failure receipt. Distribution acceptance does not establish hostile runner/CI isolation.

**Implementation plan:** [E07 tasks](../plans/2026-10-03-e07-release-distribution.md). Save acceptance in `docs/acceptance/E07.md`; use the execution contract's evidence fields and independent acceptance decision.
