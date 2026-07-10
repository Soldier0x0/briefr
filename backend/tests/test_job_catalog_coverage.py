"""JOB_CATALOG in frontend must cover every scheduler.add_job(id=...) in scheduler.py."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEDULER_PY = REPO_ROOT / "backend" / "scheduler.py"
CATALOG_JS = REPO_ROOT / "frontend" / "src" / "pages" / "admin" / "catalog.js"


def _scheduler_job_ids() -> set[str]:
    text = SCHEDULER_PY.read_text(encoding="utf-8")
    return set(re.findall(r'\bid="([a-z][a-z0-9_]*)"\s*,', text))


def _catalog_job_ids() -> set[str]:
    text = CATALOG_JS.read_text(encoding="utf-8")
    block = text.split("export const JOB_CATALOG = {", 1)[1].split("}\n\nexport function jobLabel", 1)[0]
    return set(re.findall(r"^\s+([a-z][a-z0-9_]*):\s*\{", block, re.MULTILINE))


def test_job_catalog_covers_all_scheduler_ids():
    sched_ids = _scheduler_job_ids()
    catalog_ids = _catalog_job_ids()
    missing = sorted(sched_ids - catalog_ids)
    assert not missing, f"JOB_CATALOG missing entries for scheduler jobs: {missing}"


def test_job_catalog_has_no_orphan_scheduler_keys():
    sched_ids = _scheduler_job_ids()
    catalog_ids = _catalog_job_ids()
    extra = sorted(catalog_ids - sched_ids)
    assert not extra, f"JOB_CATALOG has keys not registered in scheduler.py: {extra}"
