"""Occurrence-free Python statement IR for bounded CFG construction (schema 1)."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

STATEMENT_IR_SCHEMA = "1"
LOWERING_PRODUCER_ID = "lowering_v1_py312"

SUCCESSOR_KINDS = frozenset(
    {
        "sequential",
        "if_true",
        "if_false",
        "while_body",
        "while_exit",
        "for_body",
        "for_exit",
        "loop_else",
        "break",
        "continue",
        "return",
        "raise",
        "unreachable",
    }
)

OPERATION_KINDS = frozenset(
    {
        "name_assign",
        "name_copy",
        "constant_type",
        "value_preserving_expression",
        "call",
        "if",
        "while",
        "for",
        "break",
        "continue",
        "else",
        "return",
        "raise",
        "unknown",
    }
)


@dataclass(frozen=True)
class RelativeSpan:
    """UTF-8 byte span relative to the reviewed blob (no path or occurrence identity)."""

    start_byte: int
    end_byte: int
    start_line: int
    end_line: int
    start_column: int
    end_column: int

    def __post_init__(self) -> None:
        for name in (
            "start_byte",
            "end_byte",
            "start_line",
            "end_line",
            "start_column",
            "end_column",
        ):
            val = getattr(self, name)
            if not isinstance(val, int) or isinstance(val, bool):
                raise ValueError(f"{name} must be int, got {val!r}")
        if self.end_byte < self.start_byte:
            raise ValueError("end_byte must be >= start_byte")
        if self.start_line < 1 or self.end_line < self.start_line:
            raise ValueError("invalid line range")


@dataclass(frozen=True)
class Successor:
    kind: str
    target_id: int

    def __post_init__(self) -> None:
        if self.kind not in SUCCESSOR_KINDS:
            raise ValueError(f"unsupported successor kind {self.kind!r}")
        if self.target_id < 0:
            raise ValueError("target_id must be non-negative")


@dataclass(frozen=True)
class CallArgument:
    kind: str
    name: str | None = None
    constant_kind: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in ("name", "constant", "unknown"):
            raise ValueError(f"unsupported call argument kind {self.kind!r}")
        if self.kind == "name" and not self.name:
            raise ValueError("name argument requires name")
        if self.kind == "constant" and not self.constant_kind:
            raise ValueError("constant argument requires constant_kind")


@dataclass(frozen=True)
class CallKeyword:
    key: str
    argument: CallArgument


@dataclass(frozen=True)
class IROperation:
    """Tagged operation record; only constant kinds are persisted, never secret literals."""

    op: str
    target: str | None = None
    source_name: str | None = None
    constant_kind: str | None = None
    operator: str | None = None
    operand_names: tuple[str, ...] = ()
    callee_resolution: str | None = None
    callee_name: str | None = None
    arguments: tuple[CallArgument, ...] = ()
    keywords: tuple[CallKeyword, ...] = ()
    test_name: str | None = None
    iter_name: str | None = None
    return_name: str | None = None
    exc_name: str | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        if self.op not in OPERATION_KINDS:
            raise ValueError(f"unsupported operation {self.op!r}")


@dataclass(frozen=True)
class IRNode:
    node_id: int
    operation: IROperation
    span: RelativeSpan
    successors: tuple[Successor, ...] = ()

    def __post_init__(self) -> None:
        if self.node_id < 0:
            raise ValueError("node_id must be non-negative")


@dataclass(frozen=True)
class BindingRecord:
    name: str
    kind: str
    shadows_builtin_input: bool = False

    def __post_init__(self) -> None:
        if self.kind not in ("parameter", "local", "import", "builtin", "unknown"):
            raise ValueError(f"unsupported binding kind {self.kind!r}")


@dataclass(frozen=True)
class BoundaryRecord:
    code: str
    message: str
    span: RelativeSpan | None = None

    def __post_init__(self) -> None:
        if not self.code:
            raise ValueError("boundary code required")


@dataclass(frozen=True)
class FunctionIR:
    name: str
    parameters: tuple[str, ...]
    entry_node_id: int
    node_order: tuple[int, ...]
    nodes: tuple[IRNode, ...]
    bindings: tuple[BindingRecord, ...] = ()
    boundaries: tuple[BoundaryRecord, ...] = ()
    complete: bool = True

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("function name required")
        node_ids = {n.node_id for n in self.nodes}
        if self.entry_node_id not in node_ids:
            raise ValueError("entry_node_id must exist in nodes")
        for nid in self.node_order:
            if nid not in node_ids:
                raise ValueError(f"node_order references missing node {nid}")
        for node in self.nodes:
            for succ in node.successors:
                if succ.target_id not in node_ids and succ.kind != "unreachable":
                    raise ValueError(
                        f"successor target {succ.target_id} missing for node {node.node_id}"
                    )


@dataclass(frozen=True)
class StatementIR:
    """Occurrence-free ordered statement IR for one source blob."""

    blob_digest: str
    schema_version: str
    producer_id: str
    runtime_version: str
    functions: tuple[FunctionIR, ...]
    boundaries: tuple[BoundaryRecord, ...] = ()
    complete: bool = True

    def __post_init__(self) -> None:
        if self.schema_version != STATEMENT_IR_SCHEMA:
            raise ValueError(f"unsupported schema {self.schema_version!r}")
        if not self.producer_id:
            raise ValueError("producer_id required")
        if len(self.blob_digest) != 64:
            raise ValueError("blob_digest must be 64-char sha256 hex")


@dataclass(frozen=True)
class BoundStatementIR:
    """Coordinator-bound statement IR with validated occurrence identity."""

    ir: StatementIR
    contract_digest: str
    snapshot: str
    path: str
    side: str

    def __post_init__(self) -> None:
        if self.side not in ("base", "head"):
            raise ValueError(f"side must be 'base' or 'head', got {self.side!r}")
        if not self.contract_digest:
            raise ValueError("contract_digest required")


def statement_ir_cache_key(ir: StatementIR) -> str:
    """Deterministic cache key from blob digest and all lowering identities."""
    content = ":".join(
        (
            ir.blob_digest,
            ir.schema_version,
            ir.producer_id,
            ir.runtime_version,
        )
    )
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def bind_statement_ir(
    ir: StatementIR,
    *,
    source_bytes: bytes,
    contract_digest: str,
    snapshot: str,
    path: str,
    side: str,
) -> BoundStatementIR:
    """Validate blob digest and attach occurrence identity."""
    actual = hashlib.sha256(source_bytes).hexdigest()
    if actual != ir.blob_digest:
        raise ValueError(
            f"blob digest mismatch: expected {ir.blob_digest}, got {actual}"
        )
    return BoundStatementIR(
        ir=ir,
        contract_digest=contract_digest,
        snapshot=snapshot,
        path=path,
        side=side,
    )


def _span_to_dict(span: RelativeSpan) -> dict[str, int]:
    return {
        "start_byte": span.start_byte,
        "end_byte": span.end_byte,
        "start_line": span.start_line,
        "end_line": span.end_line,
        "start_column": span.start_column,
        "end_column": span.end_column,
    }


def _span_from_dict(raw: Mapping[str, Any]) -> RelativeSpan:
    return RelativeSpan(
        start_byte=int(raw["start_byte"]),
        end_byte=int(raw["end_byte"]),
        start_line=int(raw["start_line"]),
        end_line=int(raw["end_line"]),
        start_column=int(raw["start_column"]),
        end_column=int(raw["end_column"]),
    )


def _operation_to_dict(op: IROperation) -> dict[str, Any]:
    data: dict[str, Any] = {"op": op.op}
    if op.target is not None:
        data["target"] = op.target
    if op.source_name is not None:
        data["source_name"] = op.source_name
    if op.constant_kind is not None:
        data["constant_kind"] = op.constant_kind
    if op.operator is not None:
        data["operator"] = op.operator
    if op.operand_names:
        data["operand_names"] = list(op.operand_names)
    if op.callee_resolution is not None:
        data["callee_resolution"] = op.callee_resolution
    if op.callee_name is not None:
        data["callee_name"] = op.callee_name
    if op.arguments:
        data["arguments"] = [
            {
                "kind": a.kind,
                **({"name": a.name} if a.name else {}),
                **({"constant_kind": a.constant_kind} if a.constant_kind else {}),
            }
            for a in op.arguments
        ]
    if op.keywords:
        data["keywords"] = [
            {
                "key": kw.key,
                "argument": {
                    "kind": kw.argument.kind,
                    **({"name": kw.argument.name} if kw.argument.name else {}),
                    **(
                        {"constant_kind": kw.argument.constant_kind}
                        if kw.argument.constant_kind
                        else {}
                    ),
                },
            }
            for kw in op.keywords
        ]
    if op.test_name is not None:
        data["test_name"] = op.test_name
    if op.iter_name is not None:
        data["iter_name"] = op.iter_name
    if op.return_name is not None:
        data["return_name"] = op.return_name
    if op.exc_name is not None:
        data["exc_name"] = op.exc_name
    if op.reason is not None:
        data["reason"] = op.reason
    return data


def _operation_from_dict(raw: Mapping[str, Any]) -> IROperation:
    args = tuple(
        CallArgument(
            kind=str(a["kind"]),
            name=a.get("name"),
            constant_kind=a.get("constant_kind"),
        )
        for a in raw.get("arguments", ())
    )
    keywords = tuple(
        CallKeyword(
            key=str(kw["key"]),
            argument=CallArgument(
                kind=str(kw["argument"]["kind"]),
                name=kw["argument"].get("name"),
                constant_kind=kw["argument"].get("constant_kind"),
            ),
        )
        for kw in raw.get("keywords", ())
    )
    return IROperation(
        op=str(raw["op"]),
        target=raw.get("target"),
        source_name=raw.get("source_name"),
        constant_kind=raw.get("constant_kind"),
        operator=raw.get("operator"),
        operand_names=tuple(raw.get("operand_names", ())),
        callee_resolution=raw.get("callee_resolution"),
        callee_name=raw.get("callee_name"),
        arguments=args,
        keywords=keywords,
        test_name=raw.get("test_name"),
        iter_name=raw.get("iter_name"),
        return_name=raw.get("return_name"),
        exc_name=raw.get("exc_name"),
        reason=raw.get("reason"),
    )


def statement_ir_to_dict(ir: StatementIR) -> dict[str, Any]:
    return {
        "schema_version": ir.schema_version,
        "blob_digest": ir.blob_digest,
        "producer_id": ir.producer_id,
        "runtime_version": ir.runtime_version,
        "complete": ir.complete,
        "boundaries": [
            {
                "code": b.code,
                "message": b.message,
                **({"span": _span_to_dict(b.span)} if b.span else {}),
            }
            for b in ir.boundaries
        ],
        "functions": [
            {
                "name": fn.name,
                "parameters": list(fn.parameters),
                "entry_node_id": fn.entry_node_id,
                "node_order": list(fn.node_order),
                "complete": fn.complete,
                "bindings": [
                    {
                        "name": b.name,
                        "kind": b.kind,
                        "shadows_builtin_input": b.shadows_builtin_input,
                    }
                    for b in fn.bindings
                ],
                "boundaries": [
                    {
                        "code": b.code,
                        "message": b.message,
                        **({"span": _span_to_dict(b.span)} if b.span else {}),
                    }
                    for b in fn.boundaries
                ],
                "nodes": [
                    {
                        "node_id": node.node_id,
                        "operation": _operation_to_dict(node.operation),
                        "span": _span_to_dict(node.span),
                        "successors": [
                            {"kind": s.kind, "target_id": s.target_id}
                            for s in node.successors
                        ],
                    }
                    for node in fn.nodes
                ],
            }
            for fn in ir.functions
        ],
    }


def statement_ir_from_dict(raw: Mapping[str, Any]) -> StatementIR:
    functions: list[FunctionIR] = []
    for fn_raw in raw.get("functions", ()):
        nodes = tuple(
            IRNode(
                node_id=int(n["node_id"]),
                operation=_operation_from_dict(n["operation"]),
                span=_span_from_dict(n["span"]),
                successors=tuple(
                    Successor(kind=str(s["kind"]), target_id=int(s["target_id"]))
                    for s in n.get("successors", ())
                ),
            )
            for n in fn_raw.get("nodes", ())
        )
        functions.append(
            FunctionIR(
                name=str(fn_raw["name"]),
                parameters=tuple(fn_raw.get("parameters", ())),
                entry_node_id=int(fn_raw["entry_node_id"]),
                node_order=tuple(int(x) for x in fn_raw.get("node_order", ())),
                nodes=nodes,
                bindings=tuple(
                    BindingRecord(
                        name=str(b["name"]),
                        kind=str(b["kind"]),
                        shadows_builtin_input=bool(b.get("shadows_builtin_input", False)),
                    )
                    for b in fn_raw.get("bindings", ())
                ),
                boundaries=tuple(
                    BoundaryRecord(
                        code=str(b["code"]),
                        message=str(b["message"]),
                        span=_span_from_dict(b["span"]) if b.get("span") else None,
                    )
                    for b in fn_raw.get("boundaries", ())
                ),
                complete=bool(fn_raw.get("complete", True)),
            )
        )
    boundaries = tuple(
        BoundaryRecord(
            code=str(b["code"]),
            message=str(b["message"]),
            span=_span_from_dict(b["span"]) if b.get("span") else None,
        )
        for b in raw.get("boundaries", ())
    )
    return StatementIR(
        blob_digest=str(raw["blob_digest"]),
        schema_version=str(raw.get("schema_version", STATEMENT_IR_SCHEMA)),
        producer_id=str(raw.get("producer_id", LOWERING_PRODUCER_ID)),
        runtime_version=str(raw.get("runtime_version", "3.12.0")),
        functions=tuple(functions),
        boundaries=boundaries,
        complete=bool(raw.get("complete", True)),
    )


def load_statement_ir_fixture(path: Path | str) -> StatementIR:
    """Load a handcrafted immutable IR fixture from JSON."""
    payload = Path(path).read_bytes()
    raw = json.loads(payload.decode("utf-8"))
    return statement_ir_from_dict(raw)


def handcrafted_branch_fixture(blob_digest: str) -> StatementIR:
    """Straight-line then if/else with explicit branch successors (handcrafted)."""
    span_a = RelativeSpan(0, 1, 1, 1, 1, 2)
    span_if = RelativeSpan(2, 10, 2, 2, 1, 9)
    span_t = RelativeSpan(11, 20, 3, 3, 1, 9)
    span_f = RelativeSpan(21, 30, 4, 4, 1, 9)
    span_join = RelativeSpan(31, 40, 5, 5, 1, 9)
    nodes = (
        IRNode(
            0,
            IROperation(op="name_assign", target="flag", constant_kind="bool"),
            span_a,
            (Successor("sequential", 1),),
        ),
        IRNode(
            1,
            IROperation(op="if", test_name="flag"),
            span_if,
            (
                Successor("if_true", 2),
                Successor("if_false", 3),
            ),
        ),
        IRNode(
            2,
            IROperation(op="name_assign", target="x", constant_kind="int"),
            span_t,
            (Successor("sequential", 4),),
        ),
        IRNode(
            3,
            IROperation(op="name_assign", target="x", constant_kind="int"),
            span_f,
            (Successor("sequential", 4),),
        ),
        IRNode(
            4,
            IROperation(op="return", return_name="x"),
            span_join,
            (Successor("return", 4),),
        ),
    )
    fn = FunctionIR(
        name="branch_demo",
        parameters=(),
        entry_node_id=0,
        node_order=(0, 1, 2, 3, 4),
        nodes=nodes,
    )
    return StatementIR(
        blob_digest=blob_digest,
        schema_version=STATEMENT_IR_SCHEMA,
        producer_id="handcrafted_fixture_v1",
        runtime_version="handcrafted",
        functions=(fn,),
    )


def node_by_id(function: FunctionIR, node_id: int) -> IRNode:
    for node in function.nodes:
        if node.node_id == node_id:
            return node
    raise KeyError(node_id)


def successor_targets(function: FunctionIR, node_id: int) -> tuple[int, ...]:
    node = node_by_id(function, node_id)
    return tuple(s.target_id for s in node.successors)


def ordered_operation_names(function: FunctionIR) -> tuple[str, ...]:
    return tuple(node_by_id(function, nid).operation.op for nid in function.node_order)
