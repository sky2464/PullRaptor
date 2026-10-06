# Beta 0.1.0b1 release notes

**Status:** released and customer-path verified (BR-17). **Tag:** [v0.1.0b1](https://github.com/sky2464/PullRaptor/releases/tag/v0.1.0b1).

| Field | Value |
|---|---|
| Package version | `0.1.0b1` |
| Source revision | `4dcd8ab466a26241c9651e73696495a32127fa09` |
| Wheel | `pullraptor-0.1.0b1-py3-none-any.whl` |
| SHA-256 | `d44d6da0e6fc667a26260896cd5f4d82c35b59f8126e65ce38d92d9a8e97be24` |
| Distribution | GitHub Release only (not PyPI) |

## Install (customer path)

Download the wheel from the [v0.1.0b1 release assets](https://github.com/sky2464/PullRaptor/releases/download/v0.1.0b1/pullraptor-0.1.0b1-py3-none-any.whl) (do not install from a random repository checkout).

```bash
curl -LO https://github.com/sky2464/PullRaptor/releases/download/v0.1.0b1/pullraptor-0.1.0b1-py3-none-any.whl
curl -LO https://github.com/sky2464/PullRaptor/releases/download/v0.1.0b1/SHA256SUMS
shasum -a 256 -c SHA256SUMS

python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install --no-index pullraptor-0.1.0b1-py3-none-any.whl
pullraptor --help
```

Verify the installed package is not imported from a source tree:

```bash
python -c "import pullraptor; print(pullraptor.__file__)"
```

## What this beta includes

- Offline wheel CLI (`pullraptor`) on Python 3.12.x with Git
- Exact `--base` / `--head` review (`--exact-base`), structural and diff profiles
- Markdown, JSON, and SARIF report output
- Advisory rules PY001–PY003 (not merge-blocking accuracy claims)
- Private parser cache with deterministic canonical reports for the accepted beta subset

Scope detail: [beta-0.1-scope.json](beta-0.1-scope.json).

## What this beta does not include

- In-product GitHub PR publication (`pullraptor-publish` is shipped but **refuses by default**)
- MCP, local `--staged` / `--workdir` snapshots, container image, AI network transport
- Additional language tiers, security expansion, patch runner, hosted service, enterprise controls
- Held-out accuracy study or default defect-blocking claims

Excluded interfaces remain in the wheel for development but are gated by `pullraptor.beta_admission` unless `PULLRAPTOR_DEV_ADMIT_EXTENDED=1`.

## Evidence and support

- Acceptance dossier: [docs/acceptance/releases/beta-0.1.md](../acceptance/releases/beta-0.1.md)
- Publication receipt: [beta-0.1-publication-receipt.json](beta-0.1-publication-receipt.json)
- Post-publication verification: [beta-0.1-post-publication.md](beta-0.1-post-publication.md)
- Support: [beta-0.1-support.md](beta-0.1-support.md)

## Known limitations (beta subset)

- Full E01/E07 roadmap acceptance and complete assertion-map reconciliation remain future work
- Rules are **advisory**; do not treat findings as proven defects without independent labeling studies
- Update/rollback from a prior release (BR-18) is out of scope until a second accepted artifact exists
