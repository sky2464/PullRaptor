# Installing PullRaptor (beta 0.1.x)

**Released:** [v0.1.0b1](https://github.com/sky2464/PullRaptor/releases/tag/v0.1.0b1). Customer install path is GitHub Release assets only (not PyPI). Full scope and limitations: [beta-0.1-notes.md](releases/beta-0.1-notes.md).

## Prerequisites

- Python **3.12.x** (CPython)
- Git **2.4x** on `PATH`
- Network only for downloading the release wheel and checksum file (offline install after download)

## Install from GitHub Release

```bash
curl -LO https://github.com/sky2464/PullRaptor/releases/download/v0.1.0b1/pullraptor-0.1.0b1-py3-none-any.whl
curl -LO https://github.com/sky2464/PullRaptor/releases/download/v0.1.0b1/SHA256SUMS
shasum -a 256 -c SHA256SUMS

python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install --no-index pullraptor-0.1.0b1-py3-none-any.whl
pullraptor --help
```

Verify import path does not point at a source checkout:

```bash
python -c "import pullraptor; print(pullraptor.__file__)"
```

Published wheel SHA-256 (must match `SHA256SUMS` and [release manifest](releases/beta-0.1-release-manifest.json)):

`d44d6da0e6fc667a26260896cd5f4d82c35b59f8126e65ce38d92d9a8e97be24`

## Supported beta review command

Exact Git revision review (included in beta scope). Run from a directory inside a Git repository:

```bash
pullraptor --repo /path/to/repo --base main --head HEAD --exact-base --format markdown
```

`--staged`, `--workdir`, `pullraptor-publish`, and `pullraptor-mcp` are **not** part of the beta claim; they refuse unless `PULLRAPTOR_DEV_ADMIT_EXTENDED=1` (development only).

## Provenance

Before trusting a wheel, compare SHA-256 to [beta-0.1-release-manifest.json](releases/beta-0.1-release-manifest.json) and build receipts under `docs/acceptance/artifacts/E07/provenance/` and `docs/acceptance/artifacts/E07/builds/`.

## Uninstall

```bash
python -m pip uninstall pullraptor
rm -rf ~/.cache/pullraptor  # if present; cache is operator-owned
```
