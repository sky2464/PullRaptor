# Beta release channel recovery runbook (disposable rehearsal)

**Live publication recovery (BR-17) is not authorized by this document.** This runbook supports BR-11 disposable rehearsal only.

## Scenarios

1. **Partial upload** — stop publishing; record uploaded digests; do not overwrite version with different bytes.
2. **Ambiguous upload response** — reconcile by downloading published asset and comparing SHA-256 to candidate manifest.
3. **Defective version** — quarantine tag/assets, preserve evidence, publish corrected bytes under a **new** prerelease version.

## Operator checks

- Tag points at reviewed source OID from `docs/releases/beta-0.1-release-manifest.json`
- Asset digests match `docs/acceptance/artifacts/E07/provenance/two-build-comparison.json`
- Customer install smoke test from downloaded wheel without `PYTHONPATH` to source

## Rehearsal status

See `docs/releases/beta-0.1-recovery-rehearsal.json` (independent reviewer not_run).
