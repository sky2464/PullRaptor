"""Bounded value-specific hazard propagation over finite CFGs."""

from __future__ import annotations

from dataclasses import dataclass, field
import time

from pullraptor.models import Deadline, Limits, Span
from pullraptor.python_cfg import ControlFlow, build_cfg, cfg_predecessors, cfg_successors, merge_environments
from pullraptor.python_ir import BoundStatementIR, BindingRecord, IROperation, RelativeSpan


@dataclass(frozen=True)
class FlowLimits:
    max_nodes_per_function: int = 10_000
    max_edges_per_review: int = 100_000
    max_hazards: int = 32
    max_locations_per_function: int = 10_000
    max_transfer_applications: int = 1_000_000
    max_loop_iterations: int = 64


@dataclass(frozen=True)
class SourceSpec:
    kind: str
    callee_name: str | None = None
    hazard: str = "shell"


@dataclass(frozen=True)
class SinkSpec:
    kind: str
    callee_name: str | None = None
    hazard: str = "shell"
    argument_index: int = 0


@dataclass(frozen=True)
class SanitizerSpec:
    callee_name: str
    context: str
    removes_hazard: str
    argument_index: int = 0


@dataclass(frozen=True)
class SecurityModel:
    version: str
    rule_id: str
    sources: tuple[SourceSpec, ...] = ()
    sinks: tuple[SinkSpec, ...] = ()
    sanitizers: tuple[SanitizerSpec, ...] = ()
    limits: FlowLimits = field(default_factory=FlowLimits)


@dataclass(frozen=True)
class HazardWitness:
    hazard: str
    location: str
    value_token: int
    from_node: int
    to_node: int


@dataclass(frozen=True)
class SecurityObservation:
    claim: str
    rule: str
    model_version: str
    span: Span
    witnesses: tuple[HazardWitness, ...] = ()
    assumptions: tuple[str, ...] = ()
    boundaries: tuple[str, ...] = ()


@dataclass(frozen=True)
class FlowResult:
    observations: tuple[SecurityObservation, ...]
    complete: bool
    boundaries: tuple[str, ...]
    env_by_node: tuple[tuple[int, dict[str, frozenset[str]]], ...] = ()


@dataclass(frozen=True)
class HazardTag:
    hazard: str
    token: int


def _binding_map(bindings: tuple[BindingRecord, ...]) -> dict[str, BindingRecord]:
    return {b.name: b for b in bindings}


def _relative_to_span(bound: BoundStatementIR, rel: RelativeSpan) -> Span:
    return Span(
        path=bound.path,
        side=bound.side,
        start_line=rel.start_line,
        end_line=rel.end_line,
        start_byte=rel.start_byte,
        end_byte=rel.end_byte,
        start_column=rel.start_column,
        end_column=rel.end_column,
    )


def _tags_to_hazard_names(tags: frozenset[HazardTag]) -> frozenset[str]:
    return frozenset(t.hazard for t in tags)


def _rekey(tags: frozenset[HazardTag], token: int) -> frozenset[HazardTag]:
    return frozenset(HazardTag(hazard=t.hazard, token=token) for t in tags)


def _cap_tags(tags: frozenset[HazardTag], max_hazards: int) -> frozenset[HazardTag]:
    if len(tags) <= max_hazards:
        return tags
    return frozenset(sorted(tags, key=lambda t: (t.hazard, t.token))[:max_hazards])


def pysec001_model() -> SecurityModel:
    """Production PYSEC001: unshadowed builtin input seeds shell; subprocess sink with literal shell=True."""
    return SecurityModel(
        version="1",
        rule_id="PYSEC001",
        sources=(SourceSpec(kind="builtin_call", callee_name="input", hazard="shell"),),
        sinks=(
            SinkSpec(kind="resolved_call", callee_name="subprocess.run", hazard="shell"),
            SinkSpec(kind="resolved_call", callee_name="subprocess.Popen", hazard="shell"),
            SinkSpec(kind="resolved_call", callee_name="subprocess.call", hazard="shell"),
            SinkSpec(kind="resolved_call", callee_name="subprocess.check_call", hazard="shell"),
            SinkSpec(kind="resolved_call", callee_name="subprocess.check_output", hazard="shell"),
        ),
        sanitizers=(),
    )


def synthetic_sql_hazard_model() -> SecurityModel:
    """Test-only model with SQL hazard, sql_escape sanitizer, and execute_sql sink."""
    return SecurityModel(
        version="synthetic_sql_v1",
        rule_id="SYNTH_SQL",
        sources=(SourceSpec(kind="builtin_call", callee_name="input", hazard="sql"),),
        sinks=(SinkSpec(kind="unknown_call", callee_name="execute_sql", hazard="sql", argument_index=0),),
        sanitizers=(
            SanitizerSpec(
                callee_name="sql_escape",
                context="sql",
                removes_hazard="sql",
                argument_index=0,
            ),
        ),
    )


def synthetic_shell_hazard_model() -> SecurityModel:
    """Test-only shell hazard with sql sanitizer that cannot discharge shell."""
    return SecurityModel(
        version="synthetic_shell_v1",
        rule_id="SYNTH_SHELL",
        sources=(SourceSpec(kind="builtin_call", callee_name="input", hazard="shell"),),
        sinks=(),
        sanitizers=(
            SanitizerSpec(
                callee_name="sql_escape",
                context="sql",
                removes_hazard="sql",
                argument_index=0,
            ),
        ),
    )


class _TransferState:
    def __init__(self, model: SecurityModel) -> None:
        self.model = model
        self._next_token = 1
        self.transfer_count = 0
        self.boundaries: list[str] = []

    def fresh_token(self) -> int:
        tok = self._next_token
        self._next_token += 1
        return tok

    def bump_transfer(self) -> bool:
        self.transfer_count += 1
        return self.transfer_count > self.model.limits.max_transfer_applications


def _env_hazards(env: dict[str, frozenset[HazardTag]], name: str) -> frozenset[HazardTag]:
    return env.get(name, frozenset())


def _apply_source(
    op: IROperation,
    env: dict[str, frozenset[HazardTag]],
    bindings: dict[str, BindingRecord],
    model: SecurityModel,
    state: _TransferState,
    strong: bool,
) -> dict[str, frozenset[HazardTag]]:
    if op.target is None:
        return env
    for source in model.sources:
        if source.kind == "builtin_call" and op.callee_resolution == "builtin":
            if op.callee_name != source.callee_name:
                continue
            binding = bindings.get(op.target)
            if binding is not None and binding.shadows_builtin_input:
                continue
            token = state.fresh_token()
            tags = frozenset({HazardTag(hazard=source.hazard, token=token)})
            tags = _cap_tags(tags, model.limits.max_hazards)
            if strong:
                env[op.target] = tags
            else:
                env[op.target] = _env_hazards(env, op.target) | tags
    return env


def _apply_sanitizer(
    op: IROperation,
    env: dict[str, frozenset[HazardTag]],
    model: SecurityModel,
    state: _TransferState,
    strong: bool,
) -> dict[str, frozenset[HazardTag]]:
    if op.target is None:
        return env
    for san in model.sanitizers:
        if op.callee_name != san.callee_name:
            continue
        arg_name: str | None = None
        if san.argument_index < len(op.arguments):
            arg = op.arguments[san.argument_index]
            if arg.kind == "name":
                arg_name = arg.name
        if arg_name is None:
            continue
        incoming = _env_hazards(env, arg_name)
        token = state.fresh_token()
        cleaned = frozenset(
            HazardTag(hazard=t.hazard, token=token)
            for t in incoming
            if t.hazard != san.removes_hazard
        )
        cleaned = _cap_tags(cleaned, model.limits.max_hazards)
        if strong:
            env[op.target] = cleaned
        else:
            env[op.target] = _env_hazards(env, op.target) | cleaned
        return env
    return env


def _rhs_tags(op: IROperation, env: dict[str, frozenset[HazardTag]], state: _TransferState) -> frozenset[HazardTag]:
    if op.op == "name_copy" and op.source_name:
        return _env_hazards(env, op.source_name)
    if op.op == "name_assign" and op.source_name:
        return _env_hazards(env, op.source_name)
    if op.op == "value_preserving_expression" and op.operand_names:
        merged: frozenset[HazardTag] = frozenset()
        for name in op.operand_names:
            merged = merged | _env_hazards(env, name)
        return merged
    return frozenset()


def _transfer_node(
    op: IROperation,
    env: dict[str, frozenset[HazardTag]],
    bindings: dict[str, BindingRecord],
    model: SecurityModel,
    state: _TransferState,
    *,
    strong_assign: bool = True,
) -> dict[str, frozenset[HazardTag]]:
    if state.bump_transfer():
        state.boundaries.append("TRANSFER_CAP")
        return env

    out = dict(env)
    if len(out) > model.limits.max_locations_per_function:
        state.boundaries.append("LOCATION_CAP")
        return out

    if op.op == "call":
        out = _apply_source(op, out, bindings, model, state, strong_assign)
        if any(op.callee_name == s.callee_name for s in model.sanitizers):
            out = _apply_sanitizer(op, out, model, state, strong_assign)
            return out
        if op.callee_resolution == "unknown":
            state.boundaries.append("UNKNOWN_CALL")
            if op.target is not None:
                propagated: frozenset[HazardTag] = frozenset()
                for arg in op.arguments:
                    if arg.kind == "name" and arg.name:
                        propagated = propagated | _env_hazards(out, arg.name)
                token = state.fresh_token()
                propagated = _cap_tags(_rekey(propagated, token), model.limits.max_hazards)
                if strong_assign:
                    out[op.target] = propagated
                else:
                    out[op.target] = _env_hazards(out, op.target) | propagated
            for arg in op.arguments:
                if arg.kind == "name" and arg.name:
                    out[arg.name] = _env_hazards(out, arg.name)
        return out

    if op.op in ("name_assign", "name_copy") and op.target:
        tags = _rhs_tags(op, out, state)
        token = state.fresh_token()
        tags = _rekey(tags, token)
        tags = _cap_tags(tags, model.limits.max_hazards)
        if strong_assign:
            out[op.target] = tags
        else:
            out[op.target] = _env_hazards(out, op.target) | tags
        return out

    if op.op == "unknown":
        state.boundaries.append("UNKNOWN_OPERATION")
    return out


def _shell_true_literal(op: IROperation) -> bool:
    for kw in op.keywords:
        if kw.key == "shell" and kw.argument.kind == "constant":
            return kw.argument.constant_kind == "bool"
    return False


def _sink_matches(op: IROperation, sink: SinkSpec) -> bool:
    if sink.kind == "resolved_call":
        return op.callee_resolution == "resolved" and op.callee_name == sink.callee_name
    if sink.kind == "unknown_call":
        return op.callee_name == sink.callee_name
    return False


def _observations_at_sink(
    node_id: int,
    op: IROperation,
    env: dict[str, frozenset[HazardTag]],
    model: SecurityModel,
    cfg: ControlFlow,
    rel_span: RelativeSpan,
) -> list[SecurityObservation]:
    observations: list[SecurityObservation] = []
    if op.op != "call":
        return observations
    for sink in model.sinks:
        if not _sink_matches(op, sink):
            continue
        if sink.hazard == "shell" and not _shell_true_literal(op):
            continue
        arg_name: str | None = None
        if sink.argument_index < len(op.arguments):
            arg = op.arguments[sink.argument_index]
            if arg.kind == "name":
                arg_name = arg.name
        if arg_name is None:
            continue
        tags = _env_hazards(env, arg_name)
        matching = [t for t in tags if t.hazard == sink.hazard]
        if not matching:
            continue
        witnesses = tuple(
            HazardWitness(
                hazard=t.hazard,
                location=arg_name,
                value_token=t.token,
                from_node=node_id,
                to_node=node_id,
            )
            for t in matching
        )
        span = _relative_to_span(cfg.bound, rel_span)
        observations.append(
            SecurityObservation(
                claim=f"Modeled {sink.hazard} hazard reaches sink at {op.callee_name}",
                rule=model.rule_id,
                model_version=model.version,
                span=span,
                witnesses=witnesses,
                assumptions=("advisory_model",),
                boundaries=cfg.boundaries,
            )
        )
    return observations


def analyze_hazards(
    cfg: ControlFlow,
    model: SecurityModel,
    deadline: Deadline,
    *,
    limits: Limits | None = None,
) -> FlowResult:
    """Monotone worklist hazard analysis with witnessed value correspondence."""
    bindings = _binding_map(cfg.bindings)
    state = _TransferState(model)
    boundaries = list(cfg.boundaries)
    observations: list[SecurityObservation] = []

    if not cfg.nodes or deadline.is_work_exhausted():
        boundaries.append("DEADLINE_EXHAUSTED" if deadline.is_work_exhausted() else "EMPTY_CFG")
        return FlowResult(observations=tuple(), complete=False, boundaries=tuple(boundaries))

    node_by_id = {n.node_id: n for n in cfg.nodes}
    out_env: dict[int, dict[str, frozenset[HazardTag]]] = {}
    worklist: list[int] = sorted(node_by_id.keys())
    iterations = 0

    while worklist:
        if deadline.is_work_exhausted():
            boundaries.append("DEADLINE_EXHAUSTED")
            break
        iterations += 1
        if iterations > model.limits.max_loop_iterations * len(cfg.nodes) + len(cfg.nodes):
            boundaries.append("LOOP_ITERATION_CAP")
            break

        node_id = worklist.pop(0)
        node = node_by_id.get(node_id)
        if node is None:
            continue

        preds = cfg_predecessors(cfg, node_id)
        if preds:
            pred_envs = tuple(out_env.get(p, {}) for p in preds)
            in_env = merge_environments(pred_envs)
        else:
            in_env = {}

        op = node.operation
        if not isinstance(op, IROperation):
            boundaries.append("INVALID_OPERATION")
            continue

        strong = True
        if op.op == "call" and op.callee_resolution == "unknown" and op.target:
            strong = False

        new_out = _transfer_node(
            op, in_env, bindings, model, state, strong_assign=strong
        )
        changed = new_out != out_env.get(node_id)
        out_env[node_id] = new_out

        if state.boundaries:
            boundaries.extend(state.boundaries)
            state.boundaries.clear()

        rel = node.span
        observations.extend(
            _observations_at_sink(node_id, op, out_env[node_id], model, cfg, rel)
        )

        if changed:
            for succ_id, _kind in cfg_successors(cfg, node_id):
                if succ_id in worklist:
                    continue
                worklist.append(succ_id)

    complete = cfg.complete and not boundaries and not deadline.is_work_exhausted()
    if state.transfer_count >= model.limits.max_transfer_applications:
        complete = False

    env_snapshot = tuple(
        (nid, {k: _tags_to_hazard_names(v) for k, v in env.items()})
        for nid, env in sorted(out_env.items())
    )

    return FlowResult(
        observations=tuple(observations),
        complete=complete,
        boundaries=tuple(dict.fromkeys(boundaries)),
        env_by_node=env_snapshot,
    )


def analyze_bound_ir(
    bound: BoundStatementIR,
    model: SecurityModel,
    *,
    limits: Limits,
    deadline: Deadline,
) -> FlowResult:
    """Build CFG and analyze hazards for a bound statement IR."""
    cfg = build_cfg(bound, model, limits=limits, deadline=deadline)
    return analyze_hazards(cfg, model, deadline, limits=limits)


def hazards_at_location(result: FlowResult, node_id: int, location: str) -> frozenset[str]:
    for nid, env in result.env_by_node:
        if nid == node_id:
            return env.get(location, frozenset())
    return frozenset()
