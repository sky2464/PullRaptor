"""E05-T1 finite CFG construction and witnessed hazard propagation."""

from __future__ import annotations

import time
from pathlib import Path
import unittest

from pullraptor.models import Deadline, Limits
from pullraptor.python_cfg import build_cfg
from pullraptor.python_ir import (
    BoundStatementIR,
    CallArgument,
    FunctionIR,
    IROperation,
    IRNode,
    RelativeSpan,
    STATEMENT_IR_SCHEMA,
    StatementIR,
    Successor,
    load_statement_ir_fixture,
)
from pullraptor.security_flow import (
    FlowLimits,
    SecurityModel,
    SourceSpec,
    analyze_bound_ir,
    analyze_hazards,
    hazards_at_location,
    pysec001_model,
    synthetic_shell_hazard_model,
    synthetic_sql_hazard_model,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "security" / "flow"


def _bound_from_fixture(name: str) -> BoundStatementIR:
    ir = load_statement_ir_fixture(FIXTURES / name)
    return BoundStatementIR(
        ir=ir,
        contract_digest="contract",
        snapshot="snap",
        path=f"fixtures/{name}",
        side="head",
    )


def _deadline(seconds: float = 60.0) -> Deadline:
    return Deadline(started_at=time.monotonic(), duration_seconds=seconds)


class TestSecurityFlow(unittest.TestCase):
    def test_sanitizer_only_return_value(self) -> None:
        bound = _bound_from_fixture("synthetic_copy_chain.json")
        model = synthetic_sql_hazard_model()
        cfg = build_cfg(bound, model, limits=Limits(), deadline=_deadline())
        result = analyze_hazards(cfg, model, _deadline())
        hazards_a = hazards_at_location(result, 2, "a")
        hazards_b = hazards_at_location(result, 1, "b")
        self.assertIn("sql", hazards_a)
        self.assertNotIn("sql", hazards_b)
        self.assertTrue(result.observations)

    def test_wrong_context_sanitizer(self) -> None:
        bound = _bound_from_fixture("synthetic_copy_chain.json")
        model = synthetic_shell_hazard_model()
        cfg = build_cfg(bound, model, limits=Limits(), deadline=_deadline())
        result = analyze_hazards(cfg, model, _deadline())
        hazards_a = hazards_at_location(result, 1, "a")
        self.assertIn("shell", hazards_a)

    def test_ambiguous_alias_weak_update(self) -> None:
        span = RelativeSpan(0, 1, 1, 1, 1, 2)
        nodes = (
            IRNode(
                0,
                IROperation(
                    op="call",
                    target="a",
                    callee_resolution="builtin",
                    callee_name="input",
                    arguments=(),
                ),
                span,
                (Successor("sequential", 1),),
            ),
            IRNode(
                1,
                IROperation(
                    op="call",
                    target="b",
                    callee_resolution="unknown",
                    callee_name="alias",
                    arguments=(CallArgument(kind="name", name="a"),),
                ),
                span,
                (Successor("sequential", 2),),
            ),
            IRNode(
                2,
                IROperation(op="name_assign", target="a", constant_kind="int"),
                span,
                (Successor("sequential", 3),),
            ),
            IRNode(
                3,
                IROperation(op="return"),
                span,
                (Successor("return", 3),),
            ),
        )
        fn = FunctionIR(
            name="weak_alias",
            parameters=(),
            entry_node_id=0,
            node_order=(0, 1, 2, 3),
            nodes=nodes,
        )
        ir = StatementIR(
            blob_digest="0" * 64,
            schema_version=STATEMENT_IR_SCHEMA,
            producer_id="test",
            runtime_version="test",
            functions=(fn,),
        )
        bound = BoundStatementIR(
            ir=ir,
            contract_digest="c",
            snapshot="s",
            path="weak.py",
            side="head",
        )
        model = SecurityModel(
            version="weak_v1",
            rule_id="TEST",
            sources=(SourceSpec(kind="builtin_call", callee_name="input", hazard="shell"),),
        )
        cfg = build_cfg(bound, model, limits=Limits(), deadline=_deadline())
        result = analyze_hazards(cfg, model, _deadline())
        self.assertIn("shell", hazards_at_location(result, 3, "b"))
        self.assertNotIn("shell", hazards_at_location(result, 3, "a"))

    def test_unknown_call_propagates(self) -> None:
        bound = _bound_from_fixture("synthetic_copy_chain.json")
        model = pysec001_model()
        cfg = build_cfg(bound, model, limits=Limits(), deadline=_deadline())
        result = analyze_hazards(cfg, model, _deadline())
        self.assertIn("UNKNOWN_CALL", result.boundaries)

    def test_loop_monotone_converges(self) -> None:
        bound = _bound_from_fixture("loop_break_continue_else.json")
        model = SecurityModel(
            version="loop_v1",
            rule_id="LOOP",
            sources=(SourceSpec(kind="builtin_call", callee_name="input", hazard="tag"),),
        )
        cfg = build_cfg(bound, model, limits=Limits(), deadline=_deadline())
        result = analyze_hazards(cfg, model, _deadline())
        self.assertFalse(result.boundaries)

    def test_transfer_cap_partial(self) -> None:
        bound = _bound_from_fixture("synthetic_copy_chain.json")
        model = synthetic_sql_hazard_model()
        model = SecurityModel(
            version=model.version,
            rule_id=model.rule_id,
            sources=model.sources,
            sinks=model.sinks,
            sanitizers=model.sanitizers,
            limits=FlowLimits(max_transfer_applications=1),
        )
        cfg = build_cfg(bound, model, limits=Limits(), deadline=_deadline())
        result = analyze_hazards(cfg, model, _deadline())
        self.assertIn("TRANSFER_CAP", result.boundaries)
        self.assertFalse(result.complete)

    def test_cfg_exhausted_shared_deadline(self) -> None:
        bound = _bound_from_fixture("synthetic_copy_chain.json")
        model = synthetic_sql_hazard_model()
        exhausted = Deadline(started_at=time.monotonic() - 100.0, duration_seconds=3.0)
        cfg = build_cfg(bound, model, limits=Limits(), deadline=exhausted)
        self.assertIn("DEADLINE_EXHAUSTED", cfg.boundaries)
        result = analyze_hazards(cfg, model, exhausted)
        self.assertFalse(result.complete)


if __name__ == "__main__":
    unittest.main()
