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

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scheduler_locks import _LOCKS

BACKEND = Path(__file__).resolve().parents[1]

# The durable tasks the registry documents. Adding a Procrastinate task without
# updating this set (and the SYSTEM_DESIGN registry table) fails the first test.
DOCUMENTED_PROCRASTINATE_TASKS = {"health_ping", "stack_backfill"}


def _defined_procrastinate_tasks() -> set[str]:
    src = (BACKEND / "jobs" / "tasks.py").read_text(encoding="utf-8")
    return set(re.findall(r'@blueprint\.task\(\s*name="([^"]+)"', src))


def test_procrastinate_registry_is_current():
    assert _defined_procrastinate_tasks() == DOCUMENTED_PROCRASTINATE_TASKS, (
        "jobs/tasks.py defines a Procrastinate task not in the ownership registry — "
        "add it to DOCUMENTED_PROCRASTINATE_TASKS and the SYSTEM_DESIGN registry table."
    )


def test_scheduler_and_procrastinate_namespaces_are_disjoint():
    scheduler_ids = set(_LOCKS.keys())
    tasks = _defined_procrastinate_tasks()

    # No APScheduler job id may collide with a durable task name (bare or namespaced).
    assert scheduler_ids.isdisjoint(tasks)
    assert scheduler_ids.isdisjoint({f"jobs:{t}" for t in tasks})

    # APScheduler ids never use the durable-queue namespace prefix.
    assert all(not jid.startswith("jobs:") for jid in scheduler_ids)
