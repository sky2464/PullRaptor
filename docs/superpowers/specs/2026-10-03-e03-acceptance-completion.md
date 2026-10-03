# E03: AI context, transport and conversation acceptance specification

Date: 2026-10-03. Status: proposed child design; acceptance pending.

**Parent:** [Master plan](../../../Master-Plan.md), [product specification](2026-10-03-pullraptor-design.md), [mathematical core](../../mathematical-core.md), [security architecture](../../security-architecture.md), [evaluation](../../evaluation.md), and [execution contract](../../planning-contract.md).

## Outcome and scope

Complete pinned issue/CI context, bounded explanation/challenge sessions, context preview, strict transport and test/doc drafts. Existing ai_adapter functions/tests are partial implementation of this full parent scope. This child supersedes conflicting claims in the earlier narrow E03 spec; it does not declare prompt delimiters an injection-proof boundary or allow mandatory witness truncation. Diagram serialization belongs to E04; patch validation belongs to E06.

## Dependencies and delivery boundary

E01/E02 accepted report/context identities; exact-head CI acquisition uses a separate credentialed connector. Local explanation works without network. Remote AI requires explicit approved endpoint/address enforcement and organization consent; service mode also needs E11 policy. E04/E06 are not prerequisites for deterministic Python explanations.

## Architecture and records

Add frozen ContextBlock(id, kind, producer, source_revision, digest, serialized_bytes, mandatory, priority), ContextManifest(report_digest, head, blocks, retrieval_receipts), AIInvocationReceipt(requests_used, context_bytes, requested_output_tokens, elapsed_seconds, cost_state), and Conversation(report_digest, head, context_manifest, turns). AIReviewEnvelope(schema='ai-review/1', report, proposals, context_manifest, invocation_receipt) wraps rather than silently changes report schema 1. AIProposal remains typed untrusted content with producer/context provenance and no authority fields.

## Resource, dependency and compatibility budget

Exactly the parent defaults: at most 2 requests/invocation, 65,536 serialized aggregate context bytes, 2,048 requested output tokens/request, 60 seconds aggregate including retries. Mandatory witnesses must fit or the claim abstains; no truncation that drops relevant guards/sanitizers. Provider output ≤1,048,576 decoded bytes and shared depth/item/type bounds. Conversation retains at most 20 bounded turns and requires a new report after source drift. Proposed completion code ≤600 additional nonblank lines. No new third-party runtime package; deployment spend cap and provider retention/destinations must be explicitly set. Missing price data is `cost_unknown`.

## Acceptance criteria

Each criterion is required for the named scope. Cases are future checks; none was run in this planning change.

| ID | Required behavior and evidence |
|---|---|
| E03-A1 | Pinned source/issue/exact-head CI manifests, redacted preview and deterministic exact-byte selection reject stale/missing mandatory context; adversarial text cannot configure the adapter. |
| E03-A2 | Real transport fixtures prove redirect/proxy/address/DNS-rebinding/credential boundaries and local-profile separation; retries/output/refusal/quota cannot exceed shared budgets or promote proposal authority. |
| E03-A3 | Explain/challenge/test-doc draft flow is pinned, bounded, safely rendered and proposal-only; deterministic reports/evidence survive conflicts and optional provider failure unchanged. Default disabled execution is offline. |

## Failure and claim policy

AI unavailable/refused/timeout/quota errors are separate advisory status and cannot rewrite deterministic coverage. Optional failure does not fail an explicitly narrower deterministic profile; required requested AI remains visibly unavailable. New source head/context creates a new conversation. A valid line reference is a location observation, not evidence for the behavioral claim.

**Implementation plan:** [E03 tasks](../plans/2026-10-03-e03-acceptance-completion.md). Save acceptance in `docs/acceptance/E03.md`; use the execution contract's evidence fields and independent acceptance decision.
