"""Inert language worker fixture for E04 protocol dispatch tests.

Reads one strict JSON request from stdin and returns a schema-shaped result.
Does not parse or execute reviewed source bytes.
"""

from __future__ import annotations

import json
import sys

PROTOCOL = "pullraptor_language_worker_v1"


def main() -> None:
    raw = sys.stdin.buffer.read()
    if not raw:
        sys.exit(1)
    try:
        req = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        sys.exit(1)

    if req.get("protocol") != PROTOCOL:
        sys.exit(2)

    contract = str(req.get("contract_digest", ""))
    grammar = str(req.get("grammar_digest", ""))
    capability = str(req.get("capability", ""))
    scope_keys = req.get("scope_keys", [])
    if not isinstance(scope_keys, list):
        sys.exit(1)

    completed_keys: list[str] = []
    content_facts: list[dict[str, object]] = []
    for path in scope_keys:
        if not isinstance(path, str):
            continue
        completed_keys.append(path)
        content_facts.append(
            {
                "capability": capability,
                "path": path,
                "grammar_digest": grammar,
            }
        )

    out = {
        "protocol": PROTOCOL,
        "contract_digest": contract,
        "completed_keys": completed_keys,
        "content_facts": content_facts,
        "unsupported": [],
        "producer_digest": grammar,
    }
    sys.stdout.buffer.write(json.dumps(out, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
    sys.exit(0)


if __name__ == "__main__":
    main()
