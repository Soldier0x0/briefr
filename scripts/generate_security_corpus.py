#!/usr/bin/env python3
"""TM-1: generate the Security Architecture Corpus's *generated* layer from
live code facts -- routers, scheduler jobs, DB schema. Companion to the
hand-curated scripts/generate_architecture_map.py (a rich, manually authored
visualization) -- this script emits only machine-derivable facts as corpus
YAML under backend/security_architecture/corpus/, with origin: generated on
every record. Curated records (risks, decisions, abuse cases, trust-boundary
classifications, security controls) are a separate, human-judgment layer not
touched here -- see the corpus/*.yaml files with origin: curated.

Run: python scripts/generate_security_corpus.py
Idempotent: re-running produces byte-identical output when nothing in the
introspected code changed. backend/tests/test_security_architecture_corpus.py's
drift test regenerates to a temp dir and diffs against the committed files --
renaming a router, scheduler job, or table breaks the build until this script
is re-run.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
CORPUS_DIR = BACKEND / "security_architecture" / "corpus"

sys.path.insert(0, str(BACKEND))


# ── Pure extraction (unit-testable without the live app or filesystem) ──

def extract_scheduler_jobs(source: str) -> list[dict[str, str]]:
    """Parse `scheduler.add_job(func, ..., id="...", name="...")` calls."""
    pattern = re.compile(
        r'add_job\s*\(\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*,.*?'
        r'id\s*=\s*["\']([^"\']+)["\'].*?'
        r'name\s*=\s*["\']([^"\']+)["\']',
        re.S,
    )
    jobs = [
        {"id": job_id, "title": name, "callable": func}
        for func, job_id, name in pattern.findall(source)
    ]
    jobs.sort(key=lambda j: j["id"])
    return jobs


def extract_db_tables(source: str) -> list[str]:
    """Parse `CREATE TABLE IF NOT EXISTS <name>` statements."""
    return sorted(set(re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)", source)))


def build_components(
    routes_by_module: dict[str, list[tuple[str, str]]],
) -> list[dict[str, Any]]:
    """One component per router module. Frontend/scheduler/db are separate
    corpus files, not components here -- keeps this generator's scope to
    what FastAPI route introspection can actually prove."""
    components = []
    for module, routes in sorted(routes_by_module.items()):
        if module.startswith("fastapi."):
            continue  # framework-internal (docs/openapi), not a BRIEFR component
        comp_id = module.replace(".", "-")
        rel_path = module.replace(".", "/") + ".py"
        components.append({
            "id": comp_id,
            "title": module,
            "summary": f"FastAPI router module with {len(routes)} endpoint(s).",
            "owner": "platform",
            "status": "active",
            "origin": "generated",
            "endpoint_count": len(routes),
            "source_refs": [{"type": "file", "ref": f"backend/{rel_path}"}],
        })
    return components


def build_api_inventory(
    routes_by_module: dict[str, list[tuple[str, str]]],
) -> list[dict[str, Any]]:
    entries = []
    for module, routes in routes_by_module.items():
        if module.startswith("fastapi."):
            continue
        comp_id = module.replace(".", "-")
        for method, path in routes:
            entries.append({"method": method, "path": path, "component_id": comp_id})
    entries.sort(key=lambda e: (e["path"], e["method"]))
    return entries


def build_scheduler_jobs_yaml(jobs: list[dict[str, str]]) -> list[dict[str, Any]]:
    return [
        {
            "id": job["id"],
            "title": job["title"],
            "summary": f"Scheduled job registered in scheduler.py (id={job['id']}).",
            "owner": "platform",
            "status": "active",
            "origin": "generated",
            "source_refs": [{"type": "job", "ref": job["id"]}],
        }
        for job in jobs
    ]


def build_db_tables_yaml(tables: list[str]) -> list[dict[str, Any]]:
    return [
        {
            "id": table,
            "title": table,
            "summary": f"Database table defined in db/init.py (name={table}).",
            "owner": "platform",
            "status": "active",
            "origin": "generated",
            "source_refs": [{"type": "table", "ref": table}],
        }
        for table in tables
    ]


# ── Live introspection glue ──────────────────────────────────────────────

def _iter_route_contexts(routes: list[Any]):
    """Flatten FastAPI 0.137+ nested included-router trees for introspection
    -- same technique as tests/test_router_split.py's helper of the same
    name/purpose (duplicated, not imported: a generation script importing
    from tests/ is the wrong dependency direction)."""
    from fastapi.routing import APIRoute

    for route in routes:
        effective_route_contexts = getattr(route, "effective_route_contexts", None)
        if callable(effective_route_contexts):
            yield from effective_route_contexts()
        elif isinstance(route, APIRoute):
            yield route
        elif hasattr(route, "endpoint"):
            yield route


def live_routes_by_module() -> dict[str, list[tuple[str, str]]]:
    from main import app

    by_module: dict[str, list[tuple[str, str]]] = {}
    for ctx in _iter_route_contexts(app.routes):
        if not hasattr(ctx, "endpoint"):
            continue
        module = ctx.endpoint.__module__
        for method in sorted(getattr(ctx, "methods", []) or []):
            by_module.setdefault(module, []).append((method, ctx.path))
    for routes in by_module.values():
        routes.sort()
    return by_module


def generate(output_dir: Path) -> dict[Path, dict[str, Any]]:
    """Build the generated-layer corpus dict; write to output_dir. Returns
    the written {path: data} mapping so the drift test can compare in
    memory without a second filesystem round-trip."""
    import yaml

    routes_by_module = live_routes_by_module()
    scheduler_source = (BACKEND / "scheduler.py").read_text(encoding="utf-8")
    db_source = (BACKEND / "db" / "init.py").read_text(encoding="utf-8")

    jobs = extract_scheduler_jobs(scheduler_source)
    tables = extract_db_tables(db_source)

    outputs = {
        output_dir / "components.yaml": {
            "version": 1,
            "components": build_components(routes_by_module),
        },
        output_dir / "api_inventory.yaml": {
            "version": 1,
            "endpoints": build_api_inventory(routes_by_module),
        },
        output_dir / "scheduler_jobs.yaml": {
            "version": 1,
            "jobs": build_scheduler_jobs_yaml(jobs),
        },
        output_dir / "db_tables.yaml": {
            "version": 1,
            "tables": build_db_tables_yaml(tables),
        },
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    for path, data in outputs.items():
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            yaml.safe_dump(data, f, sort_keys=False, default_flow_style=False)

    return outputs


def main() -> None:
    outputs = generate(CORPUS_DIR)
    print(f"Wrote {len(outputs)} generated corpus file(s) to {CORPUS_DIR}")


if __name__ == "__main__":
    main()
