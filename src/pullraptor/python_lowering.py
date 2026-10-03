"""Lower admitted Python source bytes to occurrence-free StatementIR (schema 1)."""

from __future__ import annotations

import ast
import hashlib
import sys

from pullraptor.models import Deadline, Limits
from pullraptor.python_ir import (
    STATEMENT_IR_SCHEMA,
    BindingRecord,
    BoundaryRecord,
    CallArgument,
    CallKeyword,
    FunctionIR,
    IROperation,
    IRNode,
    LOWERING_PRODUCER_ID,
    RelativeSpan,
    StatementIR,
    Successor,
)


def _compute_relative_span(source_bytes: bytes, node: ast.AST) -> RelativeSpan:
    lines = source_bytes.splitlines(keepends=True)
    line_starts: list[int] = [0]
    for line in lines:
        line_starts.append(line_starts[-1] + len(line))

    lineno = getattr(node, "lineno", 1)
    end_lineno = getattr(node, "end_lineno", lineno)
    col_offset = getattr(node, "col_offset", 0)
    end_col_offset = getattr(node, "end_col_offset", col_offset)

    line_idx = max(1, min(lineno, len(lines) or 1))
    end_line_idx = max(1, min(end_lineno, len(lines) or 1))

    line_bytes = lines[line_idx - 1] if lines else b""
    end_line_bytes = lines[end_line_idx - 1] if lines else b""

    start_byte = line_starts[line_idx - 1] + col_offset
    end_byte = line_starts[end_line_idx - 1] + end_col_offset
    if end_byte < start_byte:
        end_byte = start_byte

    start_col = len(line_bytes[:col_offset].decode("utf-8", errors="replace")) + 1
    end_col = len(end_line_bytes[:end_col_offset].decode("utf-8", errors="replace")) + 1
    if end_line_idx == line_idx and end_col < start_col:
        end_col = start_col

    return RelativeSpan(
        start_byte=start_byte,
        end_byte=end_byte,
        start_line=line_idx,
        end_line=end_line_idx,
        start_column=start_col,
        end_column=end_col,
    )


class _Lowerer:
    def __init__(self, source_bytes: bytes) -> None:
        self.source = source_bytes
        self._next_id = 0
        self.nodes: dict[int, IRNode] = {}
        self.node_order: list[int] = []
        self.boundaries: list[BoundaryRecord] = []
        self.bindings: dict[str, BindingRecord] = {}
        self.import_aliases: dict[str, str] = {}
        self.complete = True
        self._loop_stack: list[dict[str, int]] = []

    def _alloc_id(self) -> int:
        nid = self._next_id
        self._next_id += 1
        return nid

    def _register(self, node: IRNode) -> int:
        self.nodes[node.node_id] = node
        self.node_order.append(node.node_id)
        return node.node_id

    def _set_successors(self, node_id: int, successors: tuple[Successor, ...]) -> None:
        old = self.nodes[node_id]
        self.nodes[node_id] = IRNode(old.node_id, old.operation, old.span, successors)

    def _bind_name(self, name: str, kind: str) -> None:
        shadows = name == "input" and kind in ("parameter", "local", "import")
        self.bindings[name] = BindingRecord(
            name=name,
            kind=kind,
            shadows_builtin_input=shadows,
        )

    def _record_boundary(self, code: str, message: str, node: ast.AST | None = None) -> None:
        span = _compute_relative_span(self.source, node) if node is not None else None
        self.boundaries.append(BoundaryRecord(code=code, message=message, span=span))
        self.complete = False

    def _link_sequential(self, from_id: int | None, to_id: int) -> None:
        if from_id is None:
            return
        self._set_successors(from_id, (Successor("sequential", to_id),))

    def _lower_expr_operation(self, node: ast.expr) -> IROperation:
        if isinstance(node, ast.Name):
            return IROperation(op="name_copy", source_name=node.id)
        if isinstance(node, ast.Constant):
            kind = type(node.value).__name__
            mapping = {
                "bool": "bool",
                "NoneType": "none",
                "int": "int",
                "float": "float",
                "str": "str",
            }
            return IROperation(op="constant_type", constant_kind=mapping.get(kind, "unknown"))
        if isinstance(node, ast.Call):
            return self._lower_call_expr(node)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not) and isinstance(
            node.operand, ast.Name
        ):
            return IROperation(
                op="value_preserving_expression",
                operator="not",
                operand_names=(node.operand.id,),
            )
        if isinstance(node, ast.BinOp) and isinstance(node.left, ast.Name) and isinstance(
            node.right, ast.Name
        ):
            op_map = {ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "/", ast.Mod: "%"}
            if type(node.op) in op_map:
                return IROperation(
                    op="value_preserving_expression",
                    operator=op_map[type(node.op)],
                    operand_names=(node.left.id, node.right.id),
                )
        self._record_boundary("UNSUPPORTED_EXPR", "expression not in supported subset", node)
        return IROperation(op="unknown", reason="unsupported_expression")

    def _resolve_callee(self, func: ast.expr) -> tuple[str, str]:
        if isinstance(func, ast.Name):
            if func.id == "input":
                return "builtin", "input"
            return "unknown", func.id
        if isinstance(func, ast.Attribute):
            base = func.value
            method = func.attr
            if isinstance(base, ast.Name):
                mod = self.import_aliases.get(base.id, base.id)
                if mod == "subprocess" and method in (
                    "run",
                    "Popen",
                    "call",
                    "check_call",
                    "check_output",
                ):
                    return "resolved", f"subprocess.{method}"
                return "unknown", f"{mod}.{method}"
        return "unknown", "dynamic"

    def _lower_call_expr(self, node: ast.Call) -> IROperation:
        resolution, callee_name = self._resolve_callee(node.func)
        args: list[CallArgument] = []
        for arg in node.args:
            if isinstance(arg, ast.Name):
                args.append(CallArgument(kind="name", name=arg.id))
            elif isinstance(arg, ast.Constant):
                kind = type(arg.value).__name__
                const_kind = "bool" if kind == "bool" else "unknown"
                if kind == "bool":
                    const_kind = "bool"
                elif kind == "int":
                    const_kind = "int"
                elif kind == "str":
                    const_kind = "str"
                args.append(CallArgument(kind="constant", constant_kind=const_kind))
            else:
                args.append(CallArgument(kind="unknown"))
        keywords: list[CallKeyword] = []
        for kw in node.keywords:
            if kw.arg is None:
                continue
            if isinstance(kw.value, ast.Name):
                keywords.append(
                    CallKeyword(
                        key=kw.arg,
                        argument=CallArgument(kind="name", name=kw.value.id),
                    )
                )
            elif isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, bool):
                keywords.append(
                    CallKeyword(
                        key=kw.arg,
                        argument=CallArgument(kind="constant", constant_kind="bool"),
                    )
                )
            else:
                keywords.append(CallKeyword(key=kw.arg, argument=CallArgument(kind="unknown")))
        return IROperation(
            op="call",
            callee_resolution=resolution,
            callee_name=callee_name,
            arguments=tuple(args),
            keywords=tuple(keywords),
        )

    def _lower_stmt_list(self, stmts: list[ast.stmt], fallthrough: int | None) -> int | None:
        prev: int | None = None
        for stmt in stmts:
            prev = self._lower_stmt(stmt, fallthrough, prev)
        return prev

    def _lower_stmt(
        self,
        stmt: ast.stmt,
        fallthrough: int | None,
        previous: int | None,
    ) -> int | None:
        span = _compute_relative_span(self.source, stmt)
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(
            stmt.targets[0], ast.Name
        ):
            target = stmt.targets[0].id
            self._bind_name(target, "local")
            rhs = self._lower_expr_operation(stmt.value)
            op = IROperation(
                op=rhs.op,
                target=target,
                source_name=rhs.source_name,
                constant_kind=rhs.constant_kind,
                operator=rhs.operator,
                operand_names=rhs.operand_names,
                callee_resolution=rhs.callee_resolution,
                callee_name=rhs.callee_name,
                arguments=rhs.arguments,
                keywords=rhs.keywords,
                reason=rhs.reason,
            )
            nid = self._register(IRNode(self._alloc_id(), op, span, ()))
            self._link_sequential(previous, nid)
            if fallthrough is not None:
                self._set_successors(nid, (Successor("sequential", fallthrough),))
            return nid
        if isinstance(stmt, ast.If):
            return self._lower_if(stmt, fallthrough, previous)
        if isinstance(stmt, ast.While):
            return self._lower_while(stmt, fallthrough, previous)
        if isinstance(stmt, ast.For):
            return self._lower_for(stmt, fallthrough, previous)
        if isinstance(stmt, ast.Break):
            if not self._loop_stack:
                self._record_boundary("BREAK_OUTSIDE_LOOP", "break without loop", stmt)
            target = self._loop_stack[-1]["break_target"] if self._loop_stack else 0
            nid = self._register(IRNode(self._alloc_id(), IROperation(op="break"), span, (Successor("break", target),)))
            self._link_sequential(previous, nid)
            return nid
        if isinstance(stmt, ast.Continue):
            if not self._loop_stack:
                self._record_boundary("CONTINUE_OUTSIDE_LOOP", "continue without loop", stmt)
            target = self._loop_stack[-1]["continue_target"] if self._loop_stack else 0
            nid = self._register(
                IRNode(self._alloc_id(), IROperation(op="continue"), span, (Successor("continue", target),))
            )
            self._link_sequential(previous, nid)
            return nid
        if isinstance(stmt, ast.Return):
            ret_name = stmt.value.id if isinstance(stmt.value, ast.Name) else None
            nid = self._alloc_id()
            self._register(
                IRNode(
                    nid,
                    IROperation(op="return", return_name=ret_name),
                    span,
                    (Successor("return", nid),),
                )
            )
            self._link_sequential(previous, nid)
            return nid
        if isinstance(stmt, ast.Raise):
            exc_name = stmt.exc.id if isinstance(stmt.exc, ast.Name) else None
            nid = self._alloc_id()
            self._register(
                IRNode(
                    nid,
                    IROperation(op="raise", exc_name=exc_name),
                    span,
                    (Successor("raise", nid),),
                )
            )
            self._link_sequential(previous, nid)
            return nid
        if isinstance(stmt, (ast.Try, ast.With, ast.AsyncFor, ast.AsyncWith)):
            self._record_boundary(
                "UNSUPPORTED_CONSTRUCT",
                f"unsupported statement {type(stmt).__name__}",
                stmt,
            )
            nid = self._register(
                IRNode(self._alloc_id(), IROperation(op="unknown", reason=type(stmt).__name__), span, ())
            )
            self._link_sequential(previous, nid)
            if fallthrough is not None:
                self._set_successors(nid, (Successor("sequential", fallthrough),))
            return nid
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
            op = self._lower_call_expr(stmt.value)
            nid = self._register(IRNode(self._alloc_id(), op, span, ()))
            self._link_sequential(previous, nid)
            if fallthrough is not None:
                self._set_successors(nid, (Successor("sequential", fallthrough),))
            return nid
        self._record_boundary("UNSUPPORTED_STMT", f"unsupported statement {type(stmt).__name__}", stmt)
        nid = self._register(
            IRNode(self._alloc_id(), IROperation(op="unknown", reason=type(stmt).__name__), span, ())
        )
        self._link_sequential(previous, nid)
        if fallthrough is not None:
            self._set_successors(nid, (Successor("sequential", fallthrough),))
        return nid

    def _lower_if(self, stmt: ast.If, fallthrough: int | None, previous: int | None) -> int:
        join_id = fallthrough if fallthrough is not None else self._alloc_id()
        test_name = stmt.test.id if isinstance(stmt.test, ast.Name) else None
        if_id = self._register(
            IRNode(
                self._alloc_id(),
                IROperation(op="if", test_name=test_name),
                _compute_relative_span(self.source, stmt),
                (),
            )
        )
        self._link_sequential(previous, if_id)
        true_entry = self._alloc_id()
        false_entry = self._alloc_id()
        self._set_successors(
            if_id,
            (
                Successor("if_true", true_entry),
                Successor("if_false", false_entry),
            ),
        )
        last_true = self._lower_stmt_list(stmt.body, join_id)
        if last_true is None:
            self.nodes[true_entry] = IRNode(
                true_entry,
                IROperation(op="unknown", reason="empty_if_body"),
                _compute_relative_span(self.source, stmt),
                (Successor("sequential", join_id),),
            )
            self.node_order.append(true_entry)
        else:
            self._link_sequential(last_true, join_id)
        last_false = self._lower_stmt_list(stmt.orelse, join_id)
        if last_false is None:
            self.nodes[false_entry] = IRNode(
                false_entry,
                IROperation(op="unknown", reason="empty_if_else"),
                _compute_relative_span(self.source, stmt),
                (Successor("sequential", join_id),),
            )
            self.node_order.append(false_entry)
        else:
            self._link_sequential(last_false, join_id)
        return if_id

    def _lower_while(self, stmt: ast.While, fallthrough: int | None, previous: int | None) -> int:
        exit_id = fallthrough if fallthrough is not None else self._alloc_id()
        header_id = self._alloc_id()
        body_entry = self._alloc_id()
        else_entry = self._alloc_id() if stmt.orelse else exit_id
        self._loop_stack.append(
            {"break_target": exit_id, "continue_target": header_id}
        )
        test_name = stmt.test.id if isinstance(stmt.test, ast.Name) else None
        while_id = self._register(
            IRNode(
                header_id,
                IROperation(op="while", test_name=test_name),
                _compute_relative_span(self.source, stmt),
                (
                    Successor("while_body", body_entry),
                    Successor("while_exit", else_entry if stmt.orelse else exit_id),
                ),
            )
        )
        self._link_sequential(previous, while_id)
        last_body = self._lower_stmt_list(stmt.body, header_id)
        if last_body is None:
            self.nodes[body_entry] = IRNode(
                body_entry,
                IROperation(op="unknown", reason="empty_while_body"),
                _compute_relative_span(self.source, stmt),
                (Successor("sequential", header_id),),
            )
            self.node_order.append(body_entry)
        else:
            self._link_sequential(last_body, header_id)
        if stmt.orelse:
            self._register(
                IRNode(
                    else_entry,
                    IROperation(op="else"),
                    _compute_relative_span(self.source, stmt.orelse[0]),
                    (Successor("loop_else", exit_id),),
                )
            )
            self._lower_stmt_list(stmt.orelse, exit_id)
        self._loop_stack.pop()
        return while_id

    def _lower_for(self, stmt: ast.For, fallthrough: int | None, previous: int | None) -> int:
        exit_id = fallthrough if fallthrough is not None else self._alloc_id()
        header_id = self._alloc_id()
        body_entry = self._alloc_id()
        target = stmt.target.id if isinstance(stmt.target, ast.Name) else None
        iter_name = stmt.iter.id if isinstance(stmt.iter, ast.Name) else None
        if target:
            self._bind_name(target, "local")
        self._loop_stack.append({"break_target": exit_id, "continue_target": header_id})
        for_id = self._register(
            IRNode(
                header_id,
                IROperation(op="for", target=target, iter_name=iter_name),
                _compute_relative_span(self.source, stmt),
                (
                    Successor("for_body", body_entry),
                    Successor("for_exit", exit_id),
                ),
            )
        )
        self._link_sequential(previous, for_id)
        last_body = self._lower_stmt_list(stmt.body, header_id)
        if last_body is None:
            self.nodes[body_entry] = IRNode(
                body_entry,
                IROperation(op="unknown", reason="empty_for_body"),
                _compute_relative_span(self.source, stmt),
                (Successor("sequential", header_id),),
            )
            self.node_order.append(body_entry)
        else:
            self._link_sequential(last_body, header_id)
        if stmt.orelse:
            else_id = self._alloc_id()
            self._register(
                IRNode(
                    else_id,
                    IROperation(op="else"),
                    _compute_relative_span(self.source, stmt.orelse[0]),
                    (Successor("loop_else", exit_id),),
                )
            )
            self._lower_stmt_list(stmt.orelse, exit_id)
        self._loop_stack.pop()
        return for_id

    def lower_function(self, node: ast.FunctionDef) -> FunctionIR:
        self.nodes = {}
        self.node_order = []
        self.boundaries = []
        self.bindings = {}
        self._next_id = 0
        self.complete = True
        self._loop_stack = []
        for arg in node.args.args:
            self._bind_name(arg.arg, "parameter")
        exit_id = self._alloc_id()
        self._register(
            IRNode(
                exit_id,
                IROperation(op="return"),
                _compute_relative_span(self.source, node),
                (Successor("return", exit_id),),
            )
        )
        first = self._lower_stmt_list(node.body, exit_id)
        entry = first if first is not None else exit_id
        ordered_nodes = tuple(self.nodes[nid] for nid in self.node_order)
        return FunctionIR(
            name=node.name,
            parameters=tuple(a.arg for a in node.args.args),
            entry_node_id=entry,
            node_order=tuple(self.node_order),
            nodes=ordered_nodes,
            bindings=tuple(self.bindings.values()),
            boundaries=tuple(self.boundaries),
            complete=self.complete,
        )

    def collect_imports(self, tree: ast.Module) -> None:
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    asname = alias.asname or alias.name.split(".")[-1]
                    self.import_aliases[asname] = alias.name
                    self._bind_name(asname, "import")
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                for alias in node.names:
                    asname = alias.asname or alias.name
                    full = f"{mod}.{alias.name}" if mod else alias.name
                    self.import_aliases[asname] = full
                    self._bind_name(asname, "import")


def lower_python_source(
    source_bytes: bytes,
    *,
    limits: Limits | None = None,
    deadline: Deadline | None = None,
) -> StatementIR:
    """Parse and lower supported Python constructs to StatementIR."""
    if limits is not None and len(source_bytes) > limits.max_blob_bytes:
        raise ValueError("source exceeds max_blob_bytes")
    if deadline is not None and deadline.is_work_exhausted():
        raise TimeoutError("lowering deadline exhausted")

    blob_digest = hashlib.sha256(source_bytes).hexdigest()
    runtime_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    tree = ast.parse(source_bytes)
    lowerer = _Lowerer(source_bytes)
    lowerer.collect_imports(tree)

    module_boundaries: list[BoundaryRecord] = []
    functions: list[FunctionIR] = []
    complete = True

    for node in tree.body:
        if isinstance(node, ast.AsyncFunctionDef):
            module_boundaries.append(
                BoundaryRecord(
                    code="ASYNC_UNSUPPORTED",
                    message="async def unsupported",
                    span=_compute_relative_span(source_bytes, node),
                )
            )
            complete = False
            continue
        if isinstance(node, ast.FunctionDef):
            functions.append(lowerer.lower_function(node))
            complete = complete and functions[-1].complete
        elif isinstance(node, (ast.ClassDef, ast.Try, ast.With)):
            module_boundaries.append(
                BoundaryRecord(
                    code="MODULE_UNSUPPORTED",
                    message=f"unsupported top-level {type(node).__name__}",
                    span=_compute_relative_span(source_bytes, node),
                )
            )
            complete = False
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        else:
            module_boundaries.append(
                BoundaryRecord(
                    code="MODULE_STMT_UNSUPPORTED",
                    message=f"unsupported module statement {type(node).__name__}",
                    span=_compute_relative_span(source_bytes, node),
                )
            )
            complete = False

    if not functions:
        module_boundaries.append(
            BoundaryRecord(code="NO_FUNCTIONS", message="no supported function definitions to lower")
        )
        complete = False

    return StatementIR(
        blob_digest=blob_digest,
        schema_version=STATEMENT_IR_SCHEMA,
        producer_id=LOWERING_PRODUCER_ID,
        runtime_version=runtime_version,
        functions=tuple(functions),
        boundaries=tuple(module_boundaries),
        complete=complete,
    )
