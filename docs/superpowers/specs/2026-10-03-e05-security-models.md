# E05: Bounded security models and external observations specification

Date: 2026-10-03. Status: proposed child design; acceptance pending.

**Parent:** [Master plan](../../../Master-Plan.md), [product specification](2026-10-03-pullraptor-design.md), [mathematical core](../../mathematical-core.md), [security architecture](../../security-architecture.md), [evaluation](../../evaluation.md), and [execution contract](../../planning-contract.md).

## Outcome and scope

Start with bounded Python source-to-sink and authorization models; local secret patterns; supported lockfile advisories; and a strict SARIF import subset. Other-language security remains unavailable until E04 facts and the corresponding model pass independent evaluation. No remote secret-validity probe, automatic scanner execution or unmodeled reachability suppression.

## Dependencies and delivery boundary

E01/E02 acceptance and the usefulness pilot precede expansion. Native Python CFG/transfer implementation is owned here; E04 is needed only for other-language facts. E03 may explain an observation but cannot validate it. Actual reproduction requires E06; advisory matching remains separate from execution exposure.

## Architecture and records

Use the owned occurrence-free `StatementIR`/coordinator-bound `BoundStatementIR` and explicit source-lowering contract in [the coordinator decisions](../../build-interfaces.md); lexical summaries cannot reconstruct a CFG. Lowering, CFG and both analyses share the invocation deadline and preserve unsupported boundaries. Use finite value/location hazard maps, monotone worklists and witnessed predecessor edges; unknown calls conservatively propagate hazards and add boundary records. Authorization is a separate must-analysis over subject/action/resource/state facts, using intersections over all modeled may-feasible predecessors. Add frozen SecurityModel(version, sources, sinks, sanitizer_contexts, external_summaries, limits), SecurityObservation(claim, rule, model_version, span, witnesses, assumptions, boundaries), and ImportedObservation(producer, version, revision, claim, span, trust). All outputs are advisory observations/proposals until matching trusted evidence supports their precise claim.

## Resource, dependency and compatibility budget

### Initial model and pattern decisions

- `PYSEC001` initially models only the shell hazard: an unshadowed built-in `input()` return seeds the value; the E01-pinned resolved `subprocess.run/Popen/call/check_call/check_output` first command argument is a sink only with literal `shell=True`. Supported transfers are local assignment, branch union, bounded loops and explicit value-preserving operations. Unknown operations retain hazards plus a boundary; no initial library sanitizer discharges an entire shell command. SQL/shell/filesystem sanitizer counterexamples in tests use synthetic trusted transfer models and do not advertise those extra production models. Interprocedural/framework behavior remains unknown.
- `AUTH001` uses a trusted, versioned declarative `AuthModel`, not inferred function names. The model specifies an exact qualified guard identity/component digest, subject/action/resource argument positions, successful boolean branch and invalidators. Only that successful branch generates the corresponding must fact. Missing/mismatched guard models, unknown concurrency/state mutation or unsupported entry/CFG remain boundaries. Initial output is always the advisory statement “Authorization not established by this model”; no runtime authorization guarantee is claimed.
- `SECRET001` matches private-key header literals `-----BEGIN PRIVATE KEY-----`, `-----BEGIN RSA PRIVATE KEY-----` or `-----BEGIN EC PRIVATE KEY-----`. `SECRET002` matches case-insensitive assignment labels `api_key`, `access_token` or `client_secret` followed by `=` or `:` and a quoted ASCII alphanumeric/underscore/hyphen value of 32–512 characters. `SECRET003` is an advisory entropy candidate only under those labels: 40–512 characters and Shannon entropy at least 4.0 bits/character. These are independently authored shape/context rules; fixtures pin exact boundaries, examples and placeholders. Emit rule/span/redacted label only, never the value or a value-derived digest.

Proposed limits: 10,000 CFG nodes/function, 100,000 edges/review, 32 hazards, 10,000 modeled locations/function and 1,000,000 transfer applications/review within the existing 60-second budget; exhaustion is partial. At most 1,500 authored analyzer lines before complexity review. Secret scanning shares 2-MiB blob limits and stores no raw values. SARIF import ≤8,388,608 bytes/depth 64/100,000 items; advisory response ≤1,048,576 bytes, ≤2 requests and 10 seconds aggregate. No new kernel packages; database/model inventories remain optional and external.

## Acceptance criteria

Each criterion is required for the named scope. Cases are future checks; none was run in this planning change.

| ID | Required behavior and evidence |
|---|---|
| E05-A1 | Finite-domain transfers are monotone, cycle termination is measured, hazards preserve value/context correspondence, unknown effects remain visible, and completed clean/cached reports match. Per-model held-out and real-repository quality evidence is recorded. |
| E05-A2 | Alternate paths, fail-open/wrong-resource/stale-state/unknown-entry cases never assert authorization; model negatives and ≥30-positive/≥30-negative-or-unknown held-out fixtures preserve advisory wording. |
| E05-A3 | Owned local patterns have false-positive/negative fixtures, value-free output and zero egress; entropy/placeholder candidates never claim credential validity. Detector strata retain explicit scope and advisory status. |
| E05-A4 | Only admitted exact ecosystem/version matches with freshness are observations; offline/stale/unknown data remains explicit. Strict SARIF subset rejects wrong revisions and hostile active fields without executing links/fixes or promoting imported trust. |

## Failure and claim policy

Limit/alias/CFG/entry gaps are explicit and required domains return exit 2. Absence of a modeled path is unknown outside a complete bounded model. Authorization not established is advisory, not an allegation of definite unauthorized access. Imported claims preserve external trust and never become independent corroboration through duplication. Initial new rules remain advisory until the evaluation contract's calibrated blocker gate passes.

**Implementation plan:** [E05 tasks](../plans/2026-10-03-e05-security-models.md). Save acceptance in `docs/acceptance/E05.md`; use the execution contract's evidence fields and independent acceptance decision.
