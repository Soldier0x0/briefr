#!/usr/bin/env python3
"""Verify every product source file has a component Q&A entry."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = Path(__file__).resolve().parent / "component_registry.json"


def expected_paths() -> set[str]:
    skip = {"tests", "alembic", ".venv", "__pycache__", "node_modules"}
    paths: set[str] = set()
    for py in (ROOT / "backend").rglob("*.py"):
        rel = py.relative_to(ROOT)
        if any(p in skip for p in rel.parts) or py.name == "__init__.py":
            continue
        paths.add(str(rel).replace("\\", "/"))
    src = ROOT / "frontend" / "src"
    for f in src.rglob("*"):
        if f.suffix not in {".jsx", ".js"} or ".test." in f.name:
            continue
        if "node_modules" in f.parts:
            continue
        paths.add(str(f.relative_to(ROOT)).replace("\\", "/"))
    sched = (ROOT / "backend/scheduler.py").read_text(encoding="utf-8")
    import re

    for jid in set(re.findall(r'\bid="([a-z0-9_]+)"', sched)):
        paths.add(f"scheduler:{jid}")
    return paths


def main() -> int:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    reg_paths = {row["path"] for row in registry}
    expected = expected_paths()
    missing = sorted(expected - reg_paths)
    extra = sorted(reg_paths - expected)
    print(f"expected: {len(expected)}")
    print(f"registry: {len(reg_paths)}")
    print(f"missing from registry: {len(missing)}")
    print(f"extra in registry: {len(extra)}")
    if missing:
        print("--- missing (first 20) ---")
        for m in missing[:20]:
            print(m)
    if missing:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
