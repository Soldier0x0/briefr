"""Job-ownership registry invariant (audit F2.2 / IDEM-C).

Two background-job systems coexist (APScheduler + Procrastinate). Each job must
be owned by exactly one system, in a disjoint namespace, so a job can never be
registered in both and double-run. This test is the executable guard behind the
registry table in docs/SYSTEM_DESIGN.md.

Import-light on purpose: ``scheduler_locks`` pulls only stdlib, and the
Procrastinate task names are read from source — so this runs without the full
backend dependency set.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scheduler_locks import _LOCKS

BACKEND = Path(__file__).resolve().parents[1]

# The durable tasks the registry documents. Adding a Procrastinate task without
# updating this set (and the SYSTEM_DESIGN registry table) fails the first test.
DOCUMENTED_PROCRASTINATE_TASKS = {
    "health_ping",
    "llm_product_extraction",
    "stack_backfill",
}

# APScheduler ticks that remain only as cron/interval enqueuers for a durable
# task of the same short name. Durable execution is still owned by jobs:<task>.
DOCUMENTED_DURABLE_ENQUEUE_TICKS = {"llm_product_extraction"}


def _defined_procrastinate_tasks() -> set[str]:
    """Parse jobs/tasks.py with ast (robust to quote style, arg order, and
    multi-line decorators) — and, unlike a naive walk, handles async def tasks."""
    src = (BACKEND / "jobs" / "tasks.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    tasks: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            if not isinstance(dec, ast.Call):
                continue
            func = dec.func
            is_task = (
                isinstance(func, ast.Attribute)
                and func.attr == "task"
                and isinstance(func.value, ast.Name)
                and func.value.id == "blueprint"
            )
            if not is_task:
                continue
            for kw in dec.keywords:
                if kw.arg == "name" and isinstance(kw.value, ast.Constant):
                    tasks.add(kw.value.value)
    return tasks


def test_procrastinate_registry_is_current():
    assert _defined_procrastinate_tasks() == DOCUMENTED_PROCRASTINATE_TASKS, (
        "jobs/tasks.py defines a Procrastinate task not in the ownership registry — "
        "add it to DOCUMENTED_PROCRASTINATE_TASKS and the SYSTEM_DESIGN registry table."
    )


def test_scheduler_and_procrastinate_namespaces_are_disjoint():
    scheduler_ids = set(_LOCKS.keys())
    tasks = _defined_procrastinate_tasks()

    # Bare-name overlap is allowed only for APScheduler ticks that enqueue the
    # durable task and do not execute the work inline when Procrastinate is on.
    assert scheduler_ids & tasks <= DOCUMENTED_DURABLE_ENQUEUE_TICKS
    assert scheduler_ids.isdisjoint({f"jobs:{t}" for t in tasks})

    # APScheduler ids never use the durable-queue namespace prefix.
    assert all(not jid.startswith("jobs:") for jid in scheduler_ids)
