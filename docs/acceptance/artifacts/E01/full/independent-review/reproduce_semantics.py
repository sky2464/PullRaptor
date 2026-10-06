"""Independent E01 checks against owned parser-data fixtures; no source execution."""
from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[6]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]

from pullraptor.evidence import decide, validate_receipts
from pullraptor.kernel import review
from pullraptor.models import BlobRef, Config, CoverageReceipt, Deadline, Limits, ReviewContract, ScopeEntry, Snapshot
from pullraptor.python_facts import bind_facts, extract_python, resolve_context
from pullraptor.rules import evaluate_rules
from tests.helpers import make_repo

OUT = Path(__file__).parent


def corpus_review():
    expected_claims = {
        "PY001": "Default mutable argument can persist across omitted-argument calls",
        "PY002": "Bare exception handler captures all exceptions including interruption",
        "PY003": "Subprocess invoked with shell=True",
    }
    cases_path = ROOT / "tests/fixtures/e01/corpus/cases.json"
    cases = json.loads(cases_path.read_bytes())
    reviewed = []
    for case in cases:
        source = case["source"].encode()
        limits = Limits()
        content = extract_python(source, limits, Deadline(time.monotonic(), 30)).content
        assert content is not None, case["id"]
        snap = Snapshot("head", (BlobRef("app.py", b"app.py", "100644", "source", len(source)),))
        bound = bind_facts(content, source, snap, "app.py", "head")
        resolved, _ = resolve_context((bound,), snap)
        findings = tuple(f for f in evaluate_rules(resolved, snap, Config()) if f.rule == case["rule"])
        assert len(findings) == case["expected_findings"], case["id"]
        for finding in findings:
            assert finding.claim == expected_claims[case["rule"]], (case["id"], finding.claim)
            assert (finding.policy_class, finding.severity, finding.state) == ("advisory", "advisory", "supported")
            assert finding.version == "1.0" and finding.assumptions and finding.witness
            assert finding.span.path == "app.py" and finding.span.side == "head"
            assert 0 <= finding.span.start_byte <= finding.span.end_byte <= len(source)
        reviewed.append({"case_id": case["id"], "rule": case["rule"], "label": case["label"],
                         "source_sha256": hashlib.sha256(source).hexdigest(),
                         "expected_findings": case["expected_findings"],
                         "expected_exact_claim": expected_claims[case["rule"]],
                         "label_decision": "accepted_for_narrow_advisory_pattern",
                         "observed_findings": len(findings), "result": "passed"})
    return {"reviewer": "beta_scope_review_independent_e01", "runtime": sys.version,
            "cases_sha256": hashlib.sha256(cases_path.read_bytes()).hexdigest(),
            "claim_limit": "Owned 60-case pattern labels only; no held-out accuracy or default-blocking acceptance",
            "cases": reviewed}


def receipt_context_replay():
    key = "file:head:6170702e7079:python_patterns"
    before = ReviewContract("base", "base", "head", "policy", "config-one", "tool-one", "structural",
                            (ScopeEntry(key, "file", "head", "python_patterns", path="app.py", path_bytes=b"app.py"),), True)
    receipt = CoverageReceipt(key, "policy", "python_patterns", "complete")
    after = replace(before, config_digest="config-two", tool_digest="tool-two")
    diagnostics = validate_receipts(after, (receipt,))
    return {"scenario": "same snapshot/scope/policy with changed semantic config and tool identity",
            "expected": "stale receipt rejected unless freshly rebound by coordinator",
            "observed_diagnostics": [d.code for d in diagnostics],
            "observed_exit": decide(after, (receipt,), (), diagnostics, Config()),
            "rejected": bool(diagnostics)}


def qualified_symbol_alignment():
    repo = make_repo({"app.py": b"def first(x=[]): x.append(1)\n"})
    try:
        base = repo.commit_ids[0]
        head = repo.commit({"app.py": b"def second(x=[]): x.append(1)\n"})
        value, _, _ = review(repo.root, base, head, exact_base=True, use_cache=False)
        findings = [f for f in value.findings if f.rule == "PY001"]
        return {"scenario": "qualified function identity changes first to second, parameter and mutation unchanged",
                "expected": "qualified symbol change does not assert the same obligation persists",
                "observed": [{"anchor": f.anchor, "delta": f.delta, "evidence_delta": f.evidence_delta,
                              "side": f.span.side, "claim": f.claim} for f in findings]}
    finally:
        repo.cleanup()


if __name__ == "__main__":
    (OUT / "independent-corpus-label-review.json").write_text(json.dumps(corpus_review(), indent=2) + "\n")
    result = {"stage": "working_tree_provisional", "acceptance": "pending",
              "receipt_context_replay": receipt_context_replay(),
              "qualified_symbol_alignment": qualified_symbol_alignment()}
    (OUT / "semantic-reproductions.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
