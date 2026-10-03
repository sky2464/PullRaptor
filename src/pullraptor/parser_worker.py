"""PullRaptor isolated Python parser worker.

Runs with Python -I -S to ensure neutral, isolated environment without site-packages.
"""

from __future__ import annotations

import ast
import base64
import hashlib
import json
import sys
from typing import Any

EXTRACTOR_DIGEST = "extractor_v1_py312"


def _compute_coordinates(source_bytes: bytes, node: ast.AST) -> dict[str, int]:
    """Calculate 1-based lines, 0-based UTF-8 byte offsets, and 1-based character columns."""
    lines = source_bytes.splitlines(keepends=True)
    line_starts: list[int] = [0]
    for line in lines:
        line_starts.append(line_starts[-1] + len(line))

    lineno = getattr(node, "lineno", 1)
    end_lineno = getattr(node, "end_lineno", lineno)
    col_offset = getattr(node, "col_offset", 0)
    end_col_offset = getattr(node, "end_col_offset", col_offset)

    # 1-based line indexing
    line_idx = max(1, min(lineno, len(lines)))
    end_line_idx = max(1, min(end_lineno, len(lines)))

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

    return {
        "start_line": line_idx,
        "end_line": end_line_idx,
        "start_byte": start_byte,
        "end_byte": end_byte,
        "start_column": start_col,
        "end_column": end_col,
    }


def parse_and_extract(source_bytes: bytes) -> dict[str, Any]:
    """Parse Python source and extract occurrence-free syntactic facts."""
    blob_digest = hashlib.sha256(source_bytes).hexdigest()
    runtime_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    try:
        tree = ast.parse(source_bytes)
    except SyntaxError as err:
        return {
            "success": False,
            "error": {
                "code": "PY_PARSE_FAILED",
                "message": f"PullRaptor: PY_PARSE_FAILED {err.filename or ''}:{err.lineno or 1}: Python {sys.version_info.major}.{sys.version_info.minor} could not parse this file; semantic review skipped.",
                "line": err.lineno or 1,
                "column": err.offset or 1,
            },
        }

    symbols: list[dict[str, Any]] = []
    imports: list[dict[str, Any]] = []
    pattern_facts: list[dict[str, Any]] = []
    unsupported_constructs: list[str] = []

    # Map aliases to module names: alias -> module
    import_aliases: dict[str, str] = {}

    # Extract imports and aliases
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                asname = alias.asname or alias.name
                import_aliases[asname] = alias.name
                imports.append({
                    "kind": "import",
                    "module": alias.name,
                    "asname": asname,
                    "level": 0,
                    "coords": _compute_coordinates(source_bytes, node),
                })
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for alias in node.names:
                asname = alias.asname or alias.name
                full_name = f"{mod}.{alias.name}" if mod else alias.name
                import_aliases[asname] = full_name
                imports.append({
                    "kind": "import_from",
                    "module": mod,
                    "name": alias.name,
                    "asname": asname,
                    "level": node.level,
                    "coords": _compute_coordinates(source_bytes, node),
                })

    # Walk functions to check PY001 (mutable default argument mutation)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            coords = _compute_coordinates(source_bytes, node)
            symbols.append({
                "kind": "function",
                "name": node.name,
                "coords": coords,
            })

            # Check defaults
            num_defaults = len(node.args.defaults)
            if num_defaults > 0:
                pos_args = node.args.args[-num_defaults:]
                for arg_def, default_val in zip(pos_args, node.args.defaults):
                    is_mutable = False
                    mut_type = None
                    if isinstance(default_val, ast.List):
                        is_mutable = True
                        mut_type = "list"
                    elif isinstance(default_val, ast.Dict):
                        is_mutable = True
                        mut_type = "dict"
                    elif isinstance(default_val, ast.Set):
                        is_mutable = True
                        mut_type = "set"
                    elif isinstance(default_val, ast.Call) and isinstance(default_val.func, ast.Name):
                        if default_val.func.id in ("list", "dict", "set"):
                            is_mutable = True
                            mut_type = default_val.func.id

                    if is_mutable and mut_type is not None:
                        param_name = arg_def.arg
                        # Check if param_name is mutated unreassigned in top-level body of function
                        # First: check if param_name is reassigned in node.body
                        reassigned = False
                        mutated = False
                        mutation_witness = ""

                        for stmt in node.body:
                            if isinstance(stmt, ast.Assign):
                                for target in stmt.targets:
                                    if isinstance(target, ast.Name) and target.id == param_name:
                                        reassigned = True
                                        break
                                    elif isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name) and target.value.id == param_name:
                                        if not reassigned:
                                            mutated = True
                                            mutation_witness = f"Subscript write: {param_name}[...]"
                            elif isinstance(stmt, ast.AugAssign):
                                if isinstance(stmt.target, ast.Name) and stmt.target.id == param_name:
                                    reassigned = True
                            elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
                                call = stmt.value
                                if isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Name) and call.func.value.id == param_name:
                                    method = call.func.attr
                                    if mut_type == "list" and method in ("append", "extend", "insert", "pop", "remove", "clear", "sort", "reverse"):
                                        if not reassigned:
                                            mutated = True
                                            mutation_witness = f"List mutation: {param_name}.{method}(...)"
                                    elif mut_type == "dict" and method in ("update", "setdefault", "pop", "popitem", "clear"):
                                        if not reassigned:
                                            mutated = True
                                            mutation_witness = f"Dict mutation: {param_name}.{method}(...)"
                                    elif mut_type == "set" and method in ("add", "update", "remove", "discard", "pop", "clear"):
                                        if not reassigned:
                                            mutated = True
                                            mutation_witness = f"Set mutation: {param_name}.{method}(...)"

                        if mutated and not reassigned:
                            pattern_facts.append({
                                "rule": "PY001",
                                "version": "1.0",
                                "param": param_name,
                                "type": mut_type,
                                "coords": _compute_coordinates(source_bytes, node),
                                "witness": mutation_witness,
                            })

        # Check PY002: bare exception handler
        elif isinstance(node, ast.Try):
            for handler in node.handlers:
                # Bare except: handler.type is None or handler.type is BaseException
                is_bare = False
                if handler.type is None:
                    is_bare = True
                elif isinstance(handler.type, ast.Name) and handler.type.id == "BaseException":
                    is_bare = True

                if is_bare:
                    # Check body is straight-line statements with optional terminal return and no raise
                    has_raise = False
                    has_branching = False
                    for h_stmt in handler.body:
                        if isinstance(h_stmt, ast.Raise):
                            has_raise = True
                            break
                        if isinstance(h_stmt, (ast.If, ast.For, ast.While, ast.Try, ast.With)):
                            has_branching = True
                            break
                    if not has_raise and not has_branching:
                        pattern_facts.append({
                            "rule": "PY002",
                            "version": "1.0",
                            "coords": _compute_coordinates(source_bytes, handler),
                            "witness": "Bare exception handler with straight-line body",
                        })

        # Check PY003: subprocess call with shell=True
        elif isinstance(node, ast.Call):
            call_name = None
            is_subp = False
            if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
                obj_name = node.func.value.id
                method_name = node.func.attr
                # Check if obj_name is subprocess or alias for subprocess
                orig_mod = import_aliases.get(obj_name, obj_name)
                if orig_mod == "subprocess" and method_name in ("run", "Popen", "call", "check_call", "check_output"):
                    is_subp = True
                    call_name = method_name
            elif isinstance(node.func, ast.Name):
                # e.g. from subprocess import run
                orig_target = import_aliases.get(node.func.id, "")
                if orig_target.startswith("subprocess."):
                    func_target = orig_target.split(".", 1)[1]
                    if func_target in ("run", "Popen", "call", "check_call", "check_output"):
                        is_subp = True
                        call_name = func_target

            if is_subp and call_name:
                for kw in node.keywords:
                    if kw.arg == "shell":
                        if isinstance(kw.value, ast.Constant) and kw.value.value is True:
                            pattern_facts.append({
                                "rule": "PY003",
                                "version": "1.0",
                                "call": call_name,
                                "coords": _compute_coordinates(source_bytes, node),
                                "witness": f"subprocess.{call_name}(..., shell=True)",
                            })

    return {
        "success": True,
        "content": {
            "blob_digest": blob_digest,
            "runtime_version": runtime_version,
            "schema_version": "1",
            "extractor_digest": EXTRACTOR_DIGEST,
            "symbols": symbols,
            "imports": imports,
            "pattern_facts": pattern_facts,
            "unsupported_constructs": unsupported_constructs,
            "relative_locations": [],
        },
    }


def main() -> None:
    """CLI worker protocol handler."""
    raw_in = sys.stdin.buffer.read()
    if not raw_in:
        sys.exit(1)

    try:
        req = json.loads(raw_in.decode("utf-8"))
    except Exception:
        sys.exit(1)

    if req.get("protocol") != "pullraptor_worker_v1":
        sys.exit(2)

    source_b64 = req.get("source_base64", "")
    try:
        source_bytes = base64.b64decode(source_b64)
    except Exception:
        sys.exit(1)

    res = parse_and_extract(source_bytes)
    out_payload = {
        "protocol": "pullraptor_worker_v1",
        **res,
    }
    sys.stdout.buffer.write(json.dumps(out_payload).encode("utf-8"))
    sys.exit(0)


if __name__ == "__main__":
    main()
