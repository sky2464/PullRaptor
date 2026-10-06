# Beta 0.1.0b1 post-publication verification (BR-17)

Date: 2026-10-06.

## Customer-path download

| Step | Result |
|---|---|
| Download from GitHub Release `v0.1.0b1` (not repository paths) | **passed** |
| SHA-256 vs publication receipt | **passed** (`d44d6da0…`) |
| Fresh venv `pip install` wheel only | **passed** |
| `pullraptor --help` | **passed** |
| `pullraptor-publish --help` refusal (exit 2) | **passed** |
| Offline exact-git review smoke (installed CLI, Git repo fixture) | **passed** |

## Release state

- GitHub classification: **pre-release** (`isPrerelease: true` on `v0.1.0b1`; corrected after initial publish)
- `released_verified`: **true** for declared beta subset
- Support: [beta-0.1-support.md](beta-0.1-support.md)

## Recovery

Live withdrawal not exercised; disposable rehearsal remains documented in [beta-0.1-recovery-rehearsal.json](beta-0.1-recovery-rehearsal.json).
