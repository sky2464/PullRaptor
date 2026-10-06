# Installing PullRaptor (beta 0.1.x candidate)

This document describes the **proposed** beta wheel install path. Package version metadata may still read `0.3.0` until the maintainer approves `0.1.0b1` (see `docs/releases/beta-0.1-decisions.md`).

## Prerequisites

- Python **3.12.x** (CPython)
- Git **2.4x** on `PATH`
- No network required after the wheel is available locally

## Offline install from wheel bytes

```bash
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install --no-index --find-links /path/to/wheels pullraptor
pullraptor --help
```

Verify import path does not point at a source checkout:

```bash
python -c "import pullraptor; print(pullraptor.__file__)"
```

## Supported beta review command

Exact Git revision review (included in beta scope):

```bash
pullraptor --repo /path/to/repo --base main --head HEAD --format markdown
```

`--staged`, `--workdir`, `pullraptor-publish`, and `pullraptor-mcp` are **not** part of the beta claim; they refuse unless `PULLRAPTOR_DEV_ADMIT_EXTENDED=1` (development only).

## Provenance

Before trusting a wheel, verify manifest and build receipts from `docs/acceptance/artifacts/E07/provenance/` and compare SHA-256 to downloaded bytes.

## Uninstall

```bash
python -m pip uninstall pullraptor
rm -rf ~/.cache/pullraptor  # if present; cache is operator-owned
```
