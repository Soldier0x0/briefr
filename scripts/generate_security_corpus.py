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
    """Parse `scheduler.add_job(func, ..., id="...", name="...")` calls via
    AST -- robust to argument order, formatting, and inline comments (a
    regex needing id before name in the source text was not, per review)."""
    import ast

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    jobs = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and getattr(node.func, "attr", None) == "add_job"):
            continue
        func_name = node.args[0].id if node.args and isinstance(node.args[0], ast.Name) else ""
        job_id = None
        name = None
        for kw in node.keywords:
            if kw.arg == "id" and isinstance(kw.value, ast.Constant):
                job_id = kw.value.value
            elif kw.arg == "name" and isinstance(kw.value, ast.Constant):
                name = kw.value.value
        if job_id and name:
            jobs.append({"id": job_id, "title": name, "callable": func_name})

    jobs.sort(key=lambda j: j["id"])
    return jobs


def extract_db_tables(source: str) -> list[str]:
    """Parse `CREATE TABLE IF NOT EXISTS <name>` statements -- case-insensitive,
    flexible whitespace (a developer writing lowercase SQL or extra spacing
    would otherwise be silently skipped, per review)."""
    return sorted(set(re.findall(r"(?i)CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+(\w+)", source)))


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


# ── Architecture graph (spec §4.1, §5.2 -- TM-4) ──────────────────────────
#
# Nodes are exactly the generated-layer entities already emitted above
# (components/jobs/tables) -- the TM-4 acceptance criterion "graph nodes
# match generator output exactly" holds by construction, not by a second
# hand-synced node list. Edges are `component -> table` "references" derived
# by grepping each router module's own source file for the table name
# appearing directly after a SQL keyword (FROM/JOIN/INTO/UPDATE, or
# DELETE FROM) -- anchored to real SQL syntax, not a bare substring/word
# match, so a table named e.g. `users` or `config` doesn't spuriously match
# unrelated identifiers, comments, or docstrings elsewhere in the file (the
# central "no opinion rendered as measurement" principle applies to graph
# edges too: a false negative -- a query routed through a shared helper --
# is acceptable; a false positive is not). No x/y coordinates here: layout
# is presentation, not a code fact, and doesn't belong in a drift-checked
# generated file -- the frontend computes a deterministic layout from
# cluster + index at render time.

_SQL_TABLE_REF_RE = re.compile(
    r"(?i)\b(?:FROM|JOIN|INTO|UPDATE|DELETE\s+FROM)\s+(\w+)"
)


def extract_table_refs(source: str, known_tables: set[str]) -> list[str]:
    """Table names referenced in SQL keyword position (FROM/JOIN/INTO/
    UPDATE/DELETE FROM) within `source`, restricted to `known_tables` so an
    unrelated identifier that happens to follow one of those keywords in
    non-SQL code can't slip in."""
    found: set[str] = set()
    for match in _SQL_TABLE_REF_RE.finditer(source):
        name = match.group(1)
        if name and name.lower() in known_tables:
            found.add(name.lower())
    return sorted(found)


def build_architecture_graph(
    components: list[dict[str, Any]],
    jobs_yaml: list[dict[str, Any]],
    tables_yaml: list[dict[str, Any]],
    component_source_by_id: dict[str, str],
) -> dict[str, Any]:
    """Nodes = union of components/jobs/tables (already generated above);
    edges = component->table SQL references. Deterministically sorted so
    the drift test and CI never flake on dict/set ordering."""
    known_table_ids = {t["id"] for t in tables_yaml}

    clusters = [
        {"id": "api", "label": "API Routers", "kind": "component"},
        {"id": "scheduler", "label": "Scheduler Jobs", "kind": "job"},
        {"id": "database", "label": "Database Tables", "kind": "table"},
    ]

    nodes: list[dict[str, Any]] = []
    for c in components:
        nodes.append({
            "id": c["id"],
            "label": c["title"],
            "kind": "component",
            "cluster": "api",
            "endpoint_count": c["endpoint_count"],
            "source_refs": c["source_refs"],
        })
    for j in jobs_yaml:
        nodes.append({
            "id": f"job:{j['id']}",
            "label": j["title"],
            "kind": "job",
            "cluster": "scheduler",
            "source_refs": j["source_refs"],
        })
    for t in tables_yaml:
        nodes.append({
            "id": f"table:{t['id']}",
            "label": t["title"],
            "kind": "table",
            "cluster": "database",
            "source_refs": t["source_refs"],
        })
    nodes.sort(key=lambda n: n["id"])

    edges: list[dict[str, Any]] = []
    for c in components:
        source_text = component_source_by_id.get(c["id"], "")
        for table in extract_table_refs(source_text, known_table_ids):
            edges.append({
                "id": f"{c['id']}->table:{table}",
                "source": c["id"],
                "target": f"table:{table}",
                "kind": "references_table",
            })
    edges.sort(key=lambda e: (e["source"], e["target"]))

    return {
        "version": 1,
        "clusters": clusters,
        "nodes": nodes,
        "edges": edges,
    }


# ── Self-stack (spec §4.5): BRIEFR's own CVE exposure ────────────────────
#
# Stack terms derived from BRIEFR's own dependency manifests + declared
# runtime components, fed into the *existing* `_stack_match_clause` /
# `build_threat_scenarios()` pipeline at read time (security_architecture/
# merge.py) -- no new matching or scoring code, same convention as a user's
# asset-profile stack (Forge's `profileStack`).

_RUNTIME_COMPONENTS: list[str] = ["postgresql", "nginx"]


def extract_requirements_terms(requirements_text: str) -> list[str]:
    """Bare package names from a pip requirements.txt -- strips version
    pins/extras/markers, skips comments, blank lines, and pip options
    (-r, --hash, ...)."""
    terms: set[str] = set()
    for raw_line in requirements_text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        name = re.split(r"[=<>!~\[;]", line, maxsplit=1)[0].strip()
        if name:
            terms.add(name)
    return sorted(terms)


def extract_package_json_terms(package_json_text: str) -> list[str]:
    """Package names from package.json's dependencies + devDependencies."""
    import json

    data = json.loads(package_json_text)
    names = set(data.get("dependencies", {})) | set(data.get("devDependencies", {}))
    return sorted(names)


def build_self_stack_yaml(
    requirements_terms: list[str],
    package_json_terms: list[str],
    runtime_components: list[str],
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    for source, terms in (
        ("backend/requirements.txt", requirements_terms),
        ("frontend/package.json", package_json_terms),
        ("declared runtime component", runtime_components),
    ):
        for term in terms:
            slug = re.sub(r"[^a-z0-9]+", "-", term.lower()).strip("-")
            entry_id = f"self-stack-{slug}"
            if entry_id in seen:
                continue
            seen.add(entry_id)
            entries.append({
                "id": entry_id,
                "title": term,
                "summary": f"BRIEFR dependency term derived from {source}.",
                "owner": "platform",
                "status": "active",
                "origin": "generated",
                "term": term,
                "source": source,
            })
    entries.sort(key=lambda e: e["id"])
    return entries


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
    requirements_text = (BACKEND / "requirements.txt").read_text(encoding="utf-8")
    package_json_text = (ROOT / "frontend" / "package.json").read_text(encoding="utf-8")

    jobs = extract_scheduler_jobs(scheduler_source)
    tables = extract_db_tables(db_source)
    requirements_terms = extract_requirements_terms(requirements_text)
    package_json_terms = extract_package_json_terms(package_json_text)

    components = build_components(routes_by_module)
    jobs_yaml = build_scheduler_jobs_yaml(jobs)
    tables_yaml = build_db_tables_yaml(tables)

    component_source_by_id: dict[str, str] = {}
    for c in components:
        rel_path = c["source_refs"][0]["ref"]  # "backend/routers/foo.py"
        abs_path = ROOT / rel_path
        if abs_path.exists():
            component_source_by_id[c["id"]] = abs_path.read_text(encoding="utf-8")

    architecture_graph = build_architecture_graph(
        components, jobs_yaml, tables_yaml, component_source_by_id
    )

    outputs = {
        output_dir / "components.yaml": {
            "version": 1,
            "components": components,
        },
        output_dir / "api_inventory.yaml": {
            "version": 1,
            "endpoints": build_api_inventory(routes_by_module),
        },
        output_dir / "scheduler_jobs.yaml": {
            "version": 1,
            "jobs": jobs_yaml,
        },
        output_dir / "db_tables.yaml": {
            "version": 1,
            "tables": tables_yaml,
        },
        output_dir / "self_stack.yaml": {
            "version": 1,
            "terms": build_self_stack_yaml(
                requirements_terms, package_json_terms, _RUNTIME_COMPONENTS
            ),
        },
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    for path, data in outputs.items():
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            yaml.safe_dump(data, f, sort_keys=False, default_flow_style=False)

    graph_path = output_dir / "graphs" / "architecture.json"
    graph_path.parent.mkdir(parents=True, exist_ok=True)
    with open(graph_path, "w", encoding="utf-8", newline="\n") as f:
        import json

        json.dump(architecture_graph, f, indent=2, sort_keys=False)
        f.write("\n")
    outputs[graph_path] = architecture_graph

    return outputs


def main() -> None:
    outputs = generate(CORPUS_DIR)
    print(f"Wrote {len(outputs)} generated corpus file(s) to {CORPUS_DIR}")


if __name__ == "__main__":
    main()
