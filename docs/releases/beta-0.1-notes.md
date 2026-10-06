# Beta 0.1.x release notes (draft)

**Status:** not released. **Candidate source:** `6f1b9d370f6332e88675d3bf2b681713b6840e44`.

## What this beta includes

- Offline wheel CLI (`pullraptor`) on Python 3.12.x with Git
- Exact `--base` / `--head` review, structural profile, Markdown/JSON/SARIF output
- Advisory rules PY001–PY003
- Private parser cache with deterministic canonical reports (development-verified)

## What this beta does not include

- GitHub publication, MCP, local staged/workdir snapshots, container image, AI network transport, additional languages, security expansion, patch runner, hosted service, enterprise controls
- Accuracy or default defect-blocking claims (rules remain advisory)
- Hostile CI isolation or enterprise-ready posture

## Evidence map

Claims map to artifacts under `docs/acceptance/artifacts/E01/` and `docs/acceptance/artifacts/E07/` plus `docs/releases/beta-0.1-evidence-index.json`.

## Known limitations

- Assertion map reconciliation incomplete for all 106 planned E01 test names
- Synthetic 10k-file benchmark and licensed real-repository timings **not_run**
- Independent E01/E07 acceptance **pending**
- Clean-machine Linux install **not_run**
