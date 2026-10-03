# E09: Azure Repos and Pipelines integration specification

Date: 2026-10-03. Status: proposed child design; acceptance pending.

**Parent:** [Master plan](../../../Master-Plan.md), [product specification](2026-10-03-pullraptor-design.md), [mathematical core](../../mathematical-core.md), [security architecture](../../security-architecture.md), [evaluation](../../evaluation.md), and [execution contract](../../planning-contract.md).

## Outcome and scope

Azure DevOps Services first: selected Azure Repos Git repositories, Azure Pipelines task/template, service hooks, comments/status and organization extension packaging. Server editions/versions and TFVC remain unsupported until separate compatibility evidence. Use Azure Repos build-validation/external status policies for PR enforcement, not an assumed YAML `pr` trigger.

## Dependencies and delivery boundary

E01/E02 acceptance and E07 artifact admission. Reuse E02's publication-context/lifecycle semantics through a separate platform adapter. Customer CI can precede E10 hosting; hosted hook processing requires E10/E11 remote-security essentials.

## Architecture and records

Add AzureReviewContext(organization_id, project_id, repository_id, pr_id, iteration_id, source_head, target_tip, comparison_base, policy_digest, scope_digest, reviewer_digest) independently acquired from the platform. Event payloads trigger authorized reacquisition rather than granting repo/ref authority. Separate acquisition, credential-free analysis and bounded comment/status publication. Extend the platform-neutral publication context with an explicit platform discriminator.

## Resource, dependency and compatibility budget

At most 1,048,576 hook bytes, 8,388,608 report bytes, 10 inline comments and 3 reconciled retries/30 seconds per publication. Customer analysis inherits E02 2-vCPU/4-GiB and isolation defaults. Proposed authored connector code ≤1,000 lines and extension bundle ≤5 MiB excluding E07 runtime. Inventory exact API version, task/runtime versions, action dependencies, credentials/scopes and license terms before admission; no ambient PAT in analysis.

## Acceptance criteria

Each criterion is required for the named scope. Cases are future checks; none was run in this planning change.

| ID | Required behavior and evidence |
|---|---|
| E09-A1 | Independent repository/organization authorization and exact iteration/head/base/policy/scope binding reject cross-context replay, head-preserving policy drift and expired credentials. |
| E09-A2 | Duplicate/reordered events, ambiguous POST and changed iterations are safely reconciled; line mapping and comment limits preserve truth, and incomplete analysis never emits a passing status. |
| E09-A3 | Clean install/connect/review/repeat/revoke works on the pinned Services matrix, with actual trusted-policy/credential isolation and branch-policy mapping; Server/TFVC exclusions remain explicit. |

## Failure and claim policy

Unresolved iteration/head/target/policy association rejects publication. Unsupported Server versions are unavailable, not Services-equivalent. Missing permissions, expired tokens and pipeline/hook failure are separate from analysis completion. Status cannot represent merge approval; trusted branch policy decides enforcement only for complete applicable analysis.

**Implementation plan:** [E09 tasks](../plans/2026-10-03-e09-azure-devops.md). Save acceptance in `docs/acceptance/E09.md`; use the execution contract's evidence fields and independent acceptance decision.
