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

import json
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
            "summary": (
                f"Database table created by Alembic migration (name={table})."
                if table in _MIGRATION_ONLY_TABLES
                else f"Database table defined in db/init.py (name={table})."
            ),
            "owner": "platform",
            "status": "active",
            "origin": "generated",
            "source_refs": [{"type": "table", "ref": table}],
        }
        for table in tables
    ]


# ── Architecture graph (spec §4.1, §5.2 -- TM-4) ──────────────────────────
#
# Nodes = routers + scheduler jobs + DB tables + a small allowlist of core
# backend modules + curated external intel sources. Edges:
#   - component/core/job -> table via SQL keyword refs in that source, plus
#     one-hop through same-module helpers, db.* modules, and imported
#     backend services (still SQL-keyword anchored — no fabricated deps)
#   - job -> external via a static map of known sync job ids
# False positives are not acceptable. No x/y layout in the corpus.

_SQL_TABLE_REF_RE = re.compile(
    r"(?i)\b(?:FROM|JOIN|INTO|UPDATE|DELETE\s+FROM)\s+"
    r"(?:(?:app|intel|public)\.)?(\w+)(?!\s+import\b)"
)

# Tables created by Alembic migrations rather than db/init.py. db/init.py
# defines the SQLite bootstrap schema; Postgres-only tables added by later
# migrations (e.g. app.infra_classifications in 040) live only in
# backend/alembic/versions. Curated explicitly instead of scanning the
# migrations directory: migrations also drop/rename tables and create views,
# and a scan would fabricate stale nodes.
_MIGRATION_ONLY_TABLES: frozenset[str] = frozenset({"infra_classifications"})

# Allowlisted platform modules (not every backend file — keeps the graph readable).
_CORE_MODULES: list[dict[str, str]] = [
    {
        "id": "core:auth_middleware",
        "label": "auth_middleware",
        "path": "backend/auth_middleware.py",
    },
    {
        "id": "core:dependencies",
        "label": "dependencies",
        "path": "backend/dependencies.py",
    },
    {
        "id": "core:resilient_client",
        "label": "resilient_client",
        "path": "backend/resilient_client.py",
    },
]

_EXTERNAL_SOURCES: list[dict[str, str]] = [
    {"id": "ext:nvd", "label": "NVD"},
    {"id": "ext:cisa_kev", "label": "CISA KEV"},
    {"id": "ext:epss", "label": "FIRST EPSS"},
    {"id": "ext:otx", "label": "AlienVault OTX"},
    {"id": "ext:threatfox", "label": "ThreatFox"},
]

# Deterministic job-id → external source edges (sync jobs only).
_JOB_EXTERNAL_LINKS: dict[str, list[str]] = {
    "nvd_incremental_sync": ["ext:nvd"],
    "kev_metadata_sync": ["ext:cisa_kev"],
    "kev_backlog_reconcile": ["ext:cisa_kev"],
    "epss_score_sync": ["ext:epss"],
    "otx_nightly_correlation": ["ext:otx"],
    "otx_continuous_sync": ["ext:otx"],
    "threatfox_sync": ["ext:threatfox"],
}


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


def extract_function_source(module_source: str, func_name: str) -> str:
    """Return the source text of a top-level function, or '' if missing."""
    import ast

    if not func_name or not module_source:
        return ""
    try:
        tree = ast.parse(module_source)
    except SyntaxError:
        return ""
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func_name:
            return ast.get_source_segment(module_source, node) or ""
    return ""


# Third-party / stdlib import roots — never one-hop into these for edges.
_SKIP_IMPORT_ROOTS = frozenset({
    "fastapi", "pydantic", "starlette", "uvicorn", "httpx", "apscheduler",
    "jwt", "jose", "passlib", "bcrypt", "dotenv", "yaml", "orjson", "redis",
    "asyncpg", "sqlalchemy", "alembic", "numpy", "pandas",
    "sklearn", "torch", "transformers", "openai", "groq", "bs4", "lxml",
    "feedparser", "PIL", "cv2", "asyncio", "typing", "collections",
    "dataclasses", "pathlib", "os", "sys", "re", "json", "logging",
    "datetime", "zoneinfo", "hashlib", "hmac", "base64", "uuid", "functools",
    "contextlib", "concurrent", "email", "urllib", "html", "io", "time",
    "math", "copy", "enum", "abc", "inspect", "traceback", "warnings",
    "tempfile", "shutil", "subprocess", "signal", "socket", "ssl", "secrets",
    "random", "string", "textwrap", "threading", "multiprocessing", "queue",
    "types", "operator", "itertools", "typing_extensions", "annotated_types",
})


def _read_backend_module(module: str, backend_root: Path) -> str:
    """Load `backend/<module>.py` (or package `__init__.py`); '' if missing."""
    if not module or module.split(".", 1)[0] in _SKIP_IMPORT_ROOTS:
        return ""
    parts = module.split(".")
    file_path = backend_root.joinpath(*parts).with_suffix(".py")
    if file_path.is_file():
        return file_path.read_text(encoding="utf-8")
    init_path = backend_root.joinpath(*parts) / "__init__.py"
    if init_path.is_file():
        return init_path.read_text(encoding="utf-8")
    return ""


def _top_level_import_map(module_source: str) -> dict[str, str]:
    """Map local names → dotted module paths from top-level imports only."""
    import ast

    out: dict[str, str] = {}
    if not module_source:
        return out
    try:
        tree = ast.parse(module_source)
    except SyntaxError:
        return out
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                if alias.name == "*":
                    continue
                out[alias.asname or alias.name] = node.module
        elif isinstance(node, ast.Import):
            for alias in node.names:
                local = alias.asname or alias.name.split(".", 1)[0]
                out[local] = alias.name
    return out


def _call_root_names(func_source: str) -> set[tuple[str, ...]]:
    """Attribute paths of Call expressions, e.g. db.cve.upsert → ('db','cve','upsert')."""
    import ast

    paths: set[tuple[str, ...]] = set()
    if not func_source:
        return paths
    try:
        tree = ast.parse(func_source)
    except SyntaxError:
        return paths
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        target = node.func
        names: list[str] = []
        while isinstance(target, ast.Attribute):
            names.append(target.attr)
            target = target.value
        if isinstance(target, ast.Name):
            names.append(target.id)
            paths.add(tuple(reversed(names)))
    return paths


def _db_modules_from_call_paths(
    call_paths: set[tuple[str, ...]],
    import_map: dict[str, str],
    *,
    database_shim_map: dict[str, str] | None = None,
) -> set[str]:
    mods: set[str] = set()
    database_shim_map = database_shim_map or {}
    for path in call_paths:
        if not path:
            continue
        root = path[0]
        if root == "db" and len(path) >= 2:
            # Only the imported `db` package — not a local connection var named db.
            if import_map.get("db") == "db":
                mods.add(f"db.{path[1]}")
            continue
        mapped = import_map.get(root)
        if not mapped:
            continue
        if mapped == "db" and len(path) >= 2:
            mods.add(f"db.{path[1]}")
        elif mapped.startswith("db."):
            mods.add(mapped)
        elif mapped == "database":
            # `from database import foo` → resolve foo through the shim map
            target = database_shim_map.get(root)
            if target:
                mods.add(target)
    return mods


def _backend_modules_from_call_paths(call_paths: set[tuple[str, ...]], import_map: dict[str, str]) -> set[str]:
    mods: set[str] = set()
    for path in call_paths:
        if not path:
            continue
        root = path[0]
        mapped = import_map.get(root)
        if not mapped:
            continue
        top = mapped.split(".", 1)[0]
        if top in _SKIP_IMPORT_ROOTS or top in {"db", "database"}:
            continue
        mods.add(mapped)
    return mods


def _database_shim_symbol_map(backend_root: Path) -> dict[str, str]:
    """Map symbols re-exported by backend/database.py → originating db.* module.

    Resolves both explicit imports and `import *` (via top-level function
    names defined in each star-imported db module).
    """
    import ast

    shim_src = _read_backend_module("database", backend_root)
    if not shim_src:
        return {}
    try:
        tree = ast.parse(shim_src)
    except SyntaxError:
        return {}
    mapping: dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, ast.ImportFrom) or not node.module:
            continue
        if not (node.module == "db" or node.module.startswith("db.")):
            continue
        mod = node.module if node.module.startswith("db.") else f"db.{node.names[0].name}"
        if node.module == "db":
            # from db import cve  → treat as db.cve package name if used as module
            for alias in node.names:
                if alias.name == "*":
                    continue
                mapping[alias.asname or alias.name] = f"db.{alias.name}"
            continue
        star = any(alias.name == "*" for alias in node.names)
        if star:
            mod_src = _read_backend_module(node.module, backend_root)
            if not mod_src:
                continue
            try:
                mod_tree = ast.parse(mod_src)
            except SyntaxError:
                continue
            for child in mod_tree.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    mapping.setdefault(child.name, node.module)
        else:
            for alias in node.names:
                if alias.name == "*":
                    continue
                mapping[alias.asname or alias.name] = node.module
    return mapping


def _same_module_functions_called(func_source: str, module_source: str) -> list[str]:
    """Top-level functions in `module_source` invoked as bare calls from `func_source`."""
    import ast

    if not func_source or not module_source:
        return []
    try:
        mod_tree = ast.parse(module_source)
        fn_tree = ast.parse(func_source)
    except SyntaxError:
        return []
    defined = {
        node.name
        for node in mod_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    called: list[str] = []
    seen: set[str] = set()
    for node in ast.walk(fn_tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            continue
        name = node.func.id
        if name in defined and name not in seen:
            seen.add(name)
            called.append(name)
    return called


def resolve_table_refs(
    entry_source: str,
    known_tables: set[str],
    *,
    enclosing_module_source: str | None = None,
    backend_root: Path | None = None,
) -> list[str]:
    """Table refs reachable from an entry source without fabricating edges.

    Walks:
      1) SQL keywords in the entry source
      2) same-module helpers called by the entry (job wrappers → `_run_*`)
      3) `db.*` modules imported/called from those sources
      4) one hop into other backend modules imported/called (services)

    Still SQL-keyword-anchored and restricted to `known_tables`.
    """
    backend_root = backend_root or BACKEND
    module_source = enclosing_module_source or entry_source
    import_map = _top_level_import_map(module_source)
    import_map.update(_top_level_import_map(entry_source))
    database_shim_map = _database_shim_symbol_map(backend_root)

    sources: list[str] = [entry_source]
    for fname in _same_module_functions_called(entry_source, module_source):
        body = extract_function_source(module_source, fname)
        if body:
            sources.append(body)

    found: set[str] = set()
    hop_modules: set[str] = set()
    for source in sources:
        found.update(extract_table_refs(source, known_tables))
        call_paths = _call_root_names(source)
        hop_modules.update(_db_modules_from_call_paths(
            call_paths, import_map, database_shim_map=database_shim_map,
        ))
        hop_modules.update(_backend_modules_from_call_paths(call_paths, import_map))
        for _local, mod in import_map.items():
            if mod.startswith("db."):
                hop_modules.add(mod)

    for mod in sorted(hop_modules):
        mod_src = _read_backend_module(mod, backend_root)
        if not mod_src:
            continue
        found.update(extract_table_refs(mod_src, known_tables))
        nested_map = _top_level_import_map(mod_src)
        for db_mod in _db_modules_from_call_paths(
            _call_root_names(mod_src),
            nested_map,
            database_shim_map=database_shim_map,
        ):
            db_src = _read_backend_module(db_mod, backend_root)
            if db_src:
                found.update(extract_table_refs(db_src, known_tables))
        for _local, mapped in nested_map.items():
            if mapped.startswith("db."):
                db_src = _read_backend_module(mapped, backend_root)
                if db_src:
                    found.update(extract_table_refs(db_src, known_tables))
            elif mapped == "database":
                # Service imported a database symbol — resolve via shim if we
                # also see calls; star-import coverage is via call paths above.
                pass

    return sorted(found)


def build_architecture_graph(
    components: list[dict[str, Any]],
    jobs_yaml: list[dict[str, Any]],
    tables_yaml: list[dict[str, Any]],
    component_source_by_id: dict[str, str],
    *,
    job_source_by_id: dict[str, str] | None = None,
    job_module_source: str | None = None,
    core_modules: list[dict[str, str]] | None = None,
    core_source_by_id: dict[str, str] | None = None,
    external_sources: list[dict[str, str]] | None = None,
    job_external_links: dict[str, list[str]] | None = None,
    backend_root: Path | None = None,
) -> dict[str, Any]:
    """Nodes = routers/jobs/tables + core modules + externals; edges =
    resolved SQL refs and curated job→external links. Deterministically sorted."""
    known_table_ids = {t["id"] for t in tables_yaml}
    job_source_by_id = job_source_by_id or {}
    core_modules = core_modules if core_modules is not None else _CORE_MODULES
    core_source_by_id = core_source_by_id or {}
    external_sources = (
        external_sources if external_sources is not None else _EXTERNAL_SOURCES
    )
    job_external_links = (
        job_external_links if job_external_links is not None else _JOB_EXTERNAL_LINKS
    )
    backend_root = backend_root or BACKEND

    clusters = [
        {"id": "api", "label": "API Routers", "kind": "component"},
        {"id": "core", "label": "Core Modules", "kind": "core"},
        {"id": "scheduler", "label": "Scheduler Jobs", "kind": "job"},
        {"id": "database", "label": "Database Tables", "kind": "table"},
        {"id": "external", "label": "External Sources", "kind": "external"},
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
    for core in core_modules:
        nodes.append({
            "id": core["id"],
            "label": core["label"],
            "kind": "core",
            "cluster": "core",
            "source_refs": [{"type": "file", "ref": core["path"]}],
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
    for ext in external_sources:
        nodes.append({
            "id": ext["id"],
            "label": ext["label"],
            "kind": "external",
            "cluster": "external",
            "source_refs": [{"type": "external", "ref": ext["id"]}],
        })
    nodes.sort(key=lambda n: n["id"])

    edges: list[dict[str, Any]] = []
    for c in components:
        source_text = component_source_by_id.get(c["id"], "")
        for table in resolve_table_refs(
            source_text, known_table_ids, backend_root=backend_root,
        ):
            edges.append({
                "id": f"{c['id']}->table:{table}",
                "source": c["id"],
                "target": f"table:{table}",
                "kind": "references_table",
            })
    for core in core_modules:
        source_text = core_source_by_id.get(core["id"], "")
        for table in resolve_table_refs(
            source_text, known_table_ids, backend_root=backend_root,
        ):
            edges.append({
                "id": f"{core['id']}->table:{table}",
                "source": core["id"],
                "target": f"table:{table}",
                "kind": "references_table",
            })
    for j in jobs_yaml:
        job_id = j["id"]
        source_text = job_source_by_id.get(job_id, "")
        for table in resolve_table_refs(
            source_text,
            known_table_ids,
            enclosing_module_source=job_module_source,
            backend_root=backend_root,
        ):
            edges.append({
                "id": f"job:{job_id}->table:{table}",
                "source": f"job:{job_id}",
                "target": f"table:{table}",
                "kind": "references_table",
            })
        for ext_id in job_external_links.get(job_id, []):
            edges.append({
                "id": f"job:{job_id}->{ext_id}",
                "source": f"job:{job_id}",
                "target": ext_id,
                "kind": "fetches_external",
            })
    edges.sort(key=lambda e: (e["source"], e["target"], e["kind"]))

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


_NPM_EXACT_VERSION_RE = re.compile(
    r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$"
)


def extract_requirements_entries(requirements_text: str) -> list[dict[str, str | None]]:
    """Package names from requirements.txt, preserving only exact == pins."""
    entries: dict[str, dict[str, str | None]] = {}
    for raw_line in requirements_text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        requirement = line.split(";", 1)[0].strip()
        name = re.split(r"[=<>!~\[]", requirement, maxsplit=1)[0].strip()
        if name:
            match = re.match(
                r"^[A-Za-z0-9_.-]+(?:\[[^\]]+\])?\s*==\s*([^,;\s]+)$",
                requirement,
            )
            version = match.group(1) if match else None
            existing = entries.get(name)
            if existing is None or (existing["version"] is None and version is not None):
                entries[name] = {"name": name, "version": version}
    return [entries[name] for name in sorted(entries)]


def extract_package_json_entries(package_json_text: str) -> list[dict[str, str | None]]:
    """Package names from package.json dependencies, preserving exact semver only."""
    data = json.loads(package_json_text)
    entries: dict[str, dict[str, str | None]] = {}
    for section in ("dependencies", "devDependencies"):
        for name, spec in data.get(section, {}).items():
            version = spec if _NPM_EXACT_VERSION_RE.match(str(spec)) else None
            existing = entries.get(name)
            if existing is None or (existing["version"] is None and version is not None):
                entries[name] = {"name": name, "version": version}
    return [entries[name] for name in sorted(entries)]


def build_self_stack_yaml(
    requirements_entries: list[dict[str, str | None]],
    package_json_entries: list[dict[str, str | None]],
    runtime_components: list[str],
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    for source, ecosystem, manifest_entries in (
        ("backend/requirements.txt", "pypi", requirements_entries),
        ("frontend/package.json", "npm", package_json_entries),
        (
            "declared runtime component",
            "runtime",
            [{"name": component, "version": None} for component in runtime_components],
        ),
    ):
        for manifest_entry in manifest_entries:
            term = manifest_entry["name"]
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
                "ecosystem": ecosystem,
                "version": manifest_entry.get("version"),
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
    tables = sorted(set(extract_db_tables(db_source)) | set(_MIGRATION_ONLY_TABLES))
    requirements_entries = extract_requirements_entries(requirements_text)
    package_json_entries = extract_package_json_entries(package_json_text)

    components = build_components(routes_by_module)
    jobs_yaml = build_scheduler_jobs_yaml(jobs)
    tables_yaml = build_db_tables_yaml(tables)

    component_source_by_id: dict[str, str] = {}
    for c in components:
        rel_path = c["source_refs"][0]["ref"]  # "backend/routers/foo.py"
        abs_path = ROOT / rel_path
        if abs_path.exists():
            component_source_by_id[c["id"]] = abs_path.read_text(encoding="utf-8")

    job_source_by_id: dict[str, str] = {}
    for job in jobs:
        body = extract_function_source(scheduler_source, job.get("callable", ""))
        if body:
            job_source_by_id[job["id"]] = body

    core_source_by_id: dict[str, str] = {}
    for core in _CORE_MODULES:
        abs_path = ROOT / core["path"]
        if abs_path.exists():
            core_source_by_id[core["id"]] = abs_path.read_text(encoding="utf-8")

    architecture_graph = build_architecture_graph(
        components,
        jobs_yaml,
        tables_yaml,
        component_source_by_id,
        job_source_by_id=job_source_by_id,
        job_module_source=scheduler_source,
        core_source_by_id=core_source_by_id,
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
                requirements_entries, package_json_entries, _RUNTIME_COMPONENTS
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
