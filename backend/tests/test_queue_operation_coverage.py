"""Guardrail: outbound resilient calls must declare queue metadata."""

from __future__ import annotations

import ast
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
SCAN_DIRS = ("feeds", "enrichment", "detection", "ai", "webhooks")
SKIP_FILES = {"resilient_client.py", "api_queue.py"}
TARGET_CALLS = {
    "resilient_get": "queue_operation",
    "resilient_request": "queue_operation",
    "await_api_slot": "operation",
}
WRAPPER_FUNCS = {
    "_fetch_json",
    "_otx_get",
    "_cvelistv5_get",
    "_vulnrichment_get",
}


def _call_name(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _has_keyword(node: ast.Call, name: str) -> bool:
    return any(kw.arg == name for kw in node.keywords)


def _violations_in_tree(tree: ast.AST, path: Path) -> list[str]:
    violations: list[str] = []
    wrapper_depth = 0

    class Visitor(ast.NodeVisitor):
        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            nonlocal wrapper_depth
            is_wrapper = node.name in WRAPPER_FUNCS
            if is_wrapper:
                wrapper_depth += 1
            self.generic_visit(node)
            if is_wrapper:
                wrapper_depth -= 1

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            self.visit_FunctionDef(node)  # type: ignore[arg-type]

        def visit_Call(self, node: ast.Call) -> None:
            name = _call_name(node)
            if name in TARGET_CALLS and wrapper_depth == 0:
                kw = TARGET_CALLS[name]
                if not _has_keyword(node, kw):
                    violations.append(f"{path}:{node.lineno} {name}() missing {kw}=")
            self.generic_visit(node)

    Visitor().visit(tree)
    return violations


def _scan_files() -> list[str]:
    violations: list[str] = []
    for dirname in SCAN_DIRS:
        root = BACKEND / dirname
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.py")):
            if path.name in SKIP_FILES or path.name.startswith("test_"):
                continue
            source = path.read_text(encoding="utf-8")
            try:
                tree = ast.parse(source, filename=str(path))
            except SyntaxError as exc:
                violations.append(f"{path}: syntax error {exc}")
                continue
            violations.extend(_violations_in_tree(tree, path))
    return violations


def test_resilient_calls_declare_queue_metadata():
    violations = _scan_files()
    assert not violations, "Queue metadata missing:\n" + "\n".join(violations)
