"""Finite control-flow graphs from coordinator-bound statement IR."""

from __future__ import annotations

from dataclasses import dataclass

from pullraptor.models import Deadline, Limits
from pullraptor.python_ir import (
    BindingRecord,
    BoundStatementIR,
    FunctionIR,
    RelativeSpan,
    node_by_id,
)

@dataclass(frozen=True)
class CFGEdge:
    src: int
    dst: int
    kind: str


@dataclass(frozen=True)
class CFGNode:
    node_id: int
    function_name: str
    ir_node_id: int
    operation: object
    span: RelativeSpan


@dataclass(frozen=True)
class ControlFlow:
    entry: int
    nodes: tuple[CFGNode, ...]
    edges: tuple[CFGEdge, ...]
    complete: bool
    boundaries: tuple[str, ...]
    bindings: tuple[BindingRecord, ...]
    function_name: str
    bound: BoundStatementIR


def _function_edges(function: FunctionIR) -> tuple[CFGEdge, ...]:
    edges: list[CFGEdge] = []
    for node in function.nodes:
        for succ in node.successors:
            if succ.kind == "unreachable":
                continue
            if succ.kind in ("return", "raise", "break", "continue"):
                edges.append(CFGEdge(node.node_id, succ.target_id, succ.kind))
            else:
                edges.append(CFGEdge(node.node_id, succ.target_id, succ.kind))
    return tuple(edges)


def _lower_function_to_cfg(
    function: FunctionIR,
    bound: BoundStatementIR,
    model: object,
    limits: Limits,
    deadline: Deadline,
) -> ControlFlow:
    flow_limits = model.limits  # SecurityModel.limits
    boundaries: list[str] = [b.code for b in function.boundaries]
    boundaries.extend(b.code for b in bound.ir.boundaries)

    if deadline.is_work_exhausted():
        boundaries.append("DEADLINE_EXHAUSTED")
        return ControlFlow(
            entry=function.entry_node_id,
            nodes=(),
            edges=(),
            complete=False,
            boundaries=tuple(boundaries),
            bindings=function.bindings,
            function_name=function.name,
            bound=bound,
        )

    if len(function.nodes) > flow_limits.max_nodes_per_function:
        boundaries.append("CFG_NODE_CAP")
        return ControlFlow(
            entry=function.entry_node_id,
            nodes=(),
            edges=(),
            complete=False,
            boundaries=tuple(boundaries),
            bindings=function.bindings,
            function_name=function.name,
            bound=bound,
        )

    edges = _function_edges(function)
    if len(edges) > flow_limits.max_edges_per_review:
        boundaries.append("CFG_EDGE_CAP")
        return ControlFlow(
            entry=function.entry_node_id,
            nodes=(),
            edges=(),
            complete=False,
            boundaries=tuple(boundaries),
            bindings=function.bindings,
            function_name=function.name,
            bound=bound,
        )

    cfg_nodes: list[CFGNode] = []
    for nid in function.node_order:
        ir_node = node_by_id(function, nid)
        cfg_nodes.append(
            CFGNode(
                node_id=ir_node.node_id,
                function_name=function.name,
                ir_node_id=ir_node.node_id,
                operation=ir_node.operation,
                span=ir_node.span,
            )
        )

    complete = function.complete and bound.ir.complete
    if boundaries:
        complete = False

    return ControlFlow(
        entry=function.entry_node_id,
        nodes=tuple(cfg_nodes),
        edges=edges,
        complete=complete,
        boundaries=tuple(boundaries),
        bindings=function.bindings,
        function_name=function.name,
        bound=bound,
    )


def build_cfg(
    ir: BoundStatementIR,
    model: object,
    *,
    limits: Limits,
    deadline: Deadline,
) -> ControlFlow:
    """Build a finite CFG for the first function in the bound IR."""
    if not ir.ir.functions:
        return ControlFlow(
            entry=0,
            nodes=(),
            edges=(),
            complete=False,
            boundaries=("NO_FUNCTIONS",),
            bindings=(),
            function_name="",
            bound=ir,
        )
    return _lower_function_to_cfg(ir.ir.functions[0], ir, model, limits, deadline)


def cfg_predecessors(cfg: ControlFlow, node_id: int) -> tuple[int, ...]:
    preds = [e.src for e in cfg.edges if e.dst == node_id]
    return tuple(sorted(preds))


def cfg_successors(cfg: ControlFlow, node_id: int) -> tuple[tuple[int, str], ...]:
    return tuple((e.dst, e.kind) for e in cfg.edges if e.src == node_id)


def merge_environments(
    envs: tuple[dict[str, frozenset], ...],
) -> dict[str, frozenset]:
    """Pointwise union join for branch/loop merge points."""
    if not envs:
        return {}
    keys: set[str] = set()
    for env in envs:
        keys.update(env.keys())
    merged: dict[str, frozenset] = {}
    for key in keys:
        merged[key] = frozenset().union(*(env.get(key, frozenset()) for env in envs))
    return merged


def deadline_now() -> float:
    return time.monotonic()
