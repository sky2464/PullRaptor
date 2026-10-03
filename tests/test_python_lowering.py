"""Tests for E05-D1 statement IR schema, fixtures, and bounded Python lowering."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest

from pullraptor.python_ir import (
    LOWERING_PRODUCER_ID,
    bind_statement_ir,
    handcrafted_branch_fixture,
    load_statement_ir_fixture,
    node_by_id,
    ordered_operation_names,
    statement_ir_cache_key,
    statement_ir_from_dict,
    statement_ir_to_dict,
    successor_targets,
)
from pullraptor.python_lowering import lower_python_source

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "security" / "flow"


class TestPythonLowering(unittest.TestCase):
    def test_statement_order_and_branch_successors(self) -> None:
        ir = load_statement_ir_fixture(FIXTURES / "branch_order.json")
        fn = ir.functions[0]
        self.assertEqual(ordered_operation_names(fn), ("name_assign", "if", "name_assign", "name_assign", "return"))
        if_node = node_by_id(fn, 1)
        kinds = {s.kind: s.target_id for s in if_node.successors}
        self.assertEqual(kinds["if_true"], 2)
        self.assertEqual(kinds["if_false"], 3)
        self.assertEqual(successor_targets(fn, 2), (4,))
        self.assertEqual(successor_targets(fn, 3), (4,))

        built = handcrafted_branch_fixture(ir.blob_digest)
        self.assertEqual(statement_ir_to_dict(built), statement_ir_to_dict(ir))

    def test_loop_break_continue_else(self) -> None:
        ir = load_statement_ir_fixture(FIXTURES / "loop_break_continue_else.json")
        fn = ir.functions[0]
        while_node = node_by_id(fn, 0)
        self.assertEqual(while_node.operation.op, "while")
        break_node = node_by_id(fn, 2)
        self.assertEqual(break_node.successors[0].kind, "break")
        self.assertEqual(break_node.successors[0].target_id, 5)
        continue_node = node_by_id(fn, 3)
        self.assertEqual(continue_node.successors[0].target_id, 0)
        else_node = node_by_id(fn, 4)
        self.assertEqual(else_node.operation.op, "else")
        self.assertEqual(else_node.successors[0].kind, "loop_else")

    def test_exception_boundary_incomplete(self) -> None:
        code = b"""
def risky():
    try:
        return 1
    except Exception:
        return 0
"""
        ir = lower_python_source(code)
        self.assertFalse(ir.complete)
        fn = ir.functions[0]
        self.assertFalse(fn.complete)
        codes = {b.code for b in fn.boundaries}
        self.assertIn("UNSUPPORTED_CONSTRUCT", codes)

    def test_ir_occurrence_free_cache_binding(self) -> None:
        ir = load_statement_ir_fixture(FIXTURES / "branch_order.json")
        serialized = json.dumps(statement_ir_to_dict(ir), sort_keys=True)
        self.assertNotIn("path", serialized)
        self.assertNotIn("snapshot", serialized)
        self.assertNotIn("side", serialized)

        key_a = statement_ir_cache_key(ir)
        key_b = statement_ir_cache_key(
            statement_ir_from_dict(statement_ir_to_dict(ir))
        )
        self.assertEqual(key_a, key_b)

        altered = statement_ir_from_dict(statement_ir_to_dict(ir))
        altered_producer = statement_ir_from_dict(
            {**statement_ir_to_dict(ir), "producer_id": "altered"}
        )
        self.assertNotEqual(statement_ir_cache_key(altered), statement_ir_cache_key(altered_producer))

        source = b"# fixture binding\n"
        digest = hashlib.sha256(source).hexdigest()
        with self.assertRaises(ValueError):
            bind_statement_ir(
                ir,
                source_bytes=source,
                contract_digest="contract",
                snapshot="snap",
                path="module.py",
                side="head",
            )
        bound = bind_statement_ir(
            statement_ir_from_dict({**statement_ir_to_dict(ir), "blob_digest": digest}),
            source_bytes=source,
            contract_digest="contract",
            snapshot="snap",
            path="module.py",
            side="head",
        )
        self.assertEqual(bound.path, "module.py")
        self.assertEqual(bound.ir.blob_digest, digest)

    def test_unicode_relative_span(self) -> None:
        code = "def f():\n    x = '\U0001f680'\n".encode()
        ir = lower_python_source(code)
        fn = ir.functions[0]
        assign_nodes = [n for n in fn.nodes if n.operation.target == "x"]
        self.assertEqual(len(assign_nodes), 1)
        span = assign_nodes[0].span
        self.assertGreater(span.end_byte, span.start_byte)
        self.assertEqual(span.start_line, 2)

    def test_shadowed_input_and_subprocess_unknown(self) -> None:
        code = b"""
import subprocess as sp

def run(input):
    data = input()
    sp(input, shell=True)
"""
        ir = lower_python_source(code)
        fn = ir.functions[0]
        input_binding = next(b for b in fn.bindings if b.name == "input")
        self.assertTrue(input_binding.shadows_builtin_input)
        param_binding = next(b for b in fn.bindings if b.name == "input")
        self.assertEqual(param_binding.kind, "parameter")
        self.assertTrue(param_binding.shadows_builtin_input)

        call_ops = [n.operation for n in fn.nodes if n.operation.op == "call"]
        self.assertTrue(call_ops)
        unknown_calls = [op for op in call_ops if op.callee_resolution == "unknown"]
        self.assertTrue(unknown_calls)

    def test_lowering_producer_identity(self) -> None:
        code = b"def ok():\n    return None\n"
        ir = lower_python_source(code)
        self.assertEqual(ir.producer_id, LOWERING_PRODUCER_ID)
        self.assertEqual(ir.schema_version, "1")
        self.assertEqual(ir.blob_digest, hashlib.sha256(code).hexdigest())


if __name__ == "__main__":
    unittest.main()
