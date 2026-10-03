# PullRaptor distribution and installation

Status: proposed customer install contract for E07-A1. This document describes supported entry points; full release provenance and clean-machine acceptance remain in the E07 child plan.

## Supported runtime

- Python **3.12.x** only until AST parser parity is accepted for newer minors.
- Git executable on the host for repository and snapshot operations.

The deterministic kernel ships with **zero** third-party Python runtime dependencies.

## Install without cloning this repository

Customers may install from a published wheel or sdist artifact:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install pullraptor==<pinned-version>
pullraptor review --help
```

Offline installation uses a downloaded wheel file:

```bash
pip install /path/to/pullraptor-<version>-py3-none-any.whl
```

## Container image

The pinned `python:3.12-slim` image copies only the `src/` tree and defaults to the CLI help entry point. Mount the customer repository at a known path; Git trust is scoped per repository via invocation flags, not a global `safe.directory` wildcard.

```bash
docker build -t pullraptor:local .
docker run --rm -v /path/to/customer/repo:/work -w /work pullraptor:local \
  pullraptor review --base main --head HEAD
```

Development and acceptance test suites are not the default container command.

## Entry points

| Command | Role |
|---|---|
| `pullraptor` | Offline review CLI |
| `pullraptor-publish` | Revision-bound publication adapter (E02) |
| `pullraptor-mcp` | Local MCP stdio adapter (E08) |
