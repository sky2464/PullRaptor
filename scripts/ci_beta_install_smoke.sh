#!/usr/bin/env bash
# Beta 0.1.x installation smoke (development CI; not independent acceptance).
set -euo pipefail

if ! pullraptor --help >/dev/null; then
  echo "ERROR: pullraptor --help failed" >&2
  exit 1
fi

if pullraptor-publish --help >/dev/null 2>&1; then
  echo "ERROR: pullraptor-publish must refuse in beta (expected exit 2)" >&2
  exit 1
fi
publish_rc=0
pullraptor-publish --help >/dev/null 2>&1 || publish_rc=$?
if [[ "$publish_rc" -ne 2 ]]; then
  echo "ERROR: pullraptor-publish --help expected exit 2, got ${publish_rc}" >&2
  exit 1
fi

if pullraptor --workdir >/dev/null 2>&1; then
  echo "ERROR: pullraptor --workdir must refuse in beta (expected exit 2)" >&2
  exit 1
fi
workdir_rc=0
pullraptor --workdir >/dev/null 2>&1 || workdir_rc=$?
if [[ "$workdir_rc" -ne 2 ]]; then
  echo "ERROR: pullraptor --workdir expected exit 2, got ${workdir_rc}" >&2
  exit 1
fi

if ! pullraptor --repo . --base HEAD~1 --head HEAD --exact-base --format json >/dev/null; then
  echo "ERROR: supported offline exact-git review flow failed" >&2
  exit 1
fi

echo "beta install smoke: excluded entrypoints refused; included review flow OK"
