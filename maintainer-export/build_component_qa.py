#!/usr/bin/env python3
"""Generate per-component interview Q&A from product source tree."""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent / "interview_qa_components.py"
REGISTRY = Path(__file__).resolve().parent / "component_registry.json"

SKIP_PARTS = {"tests", "alembic", ".venv", "__pycache__", "node_modules"}

OVERRIDES: dict[str, str] = {
    "backend/scheduler.py": "APScheduler owner — registers recurring ingest, correlation, backup, and hygiene jobs with per-job asyncio locks.",
    "backend/auth_middleware.py": "Session gate on analyst <code>/api/*</code> routes; validates <code>briefr_at</code> cookie before handlers (#441).",
    "backend/api_metering.py": "Q2 API metering — persists every <code>resilient_request</code> attempt to <code>api_call_events</code>.",
    "backend/scoring/ssvc.py": "SSVC outcome computation (Act/Attend/Track) parallel to OP — exposed on <code>/risk</code> as <code>ssvc.outcome</code>.",
    "backend/scoring/asset_match.py": "Asset profile matching for legacy Risk v1.1b and environment relevance inputs.",
    "backend/feeds/exploit_sync.py": "Orchestrates ExploitDB, Metasploit, Nuclei index, and PoC-GitHub exploit feeds under <code>exploit_sources_sync</code>.",
    "backend/feeds/incident_news.py": "Fetches and normalizes cybersecurity RSS sources for Incidents &amp; News tab.",
    "backend/services/semantic_search.py": "Hybrid semantic search orchestration over embeddings + filters (E3/E8).",
    "backend/diagnostics/support_pack.py": "Builds redacted operator support-pack ZIP (health + ring-buffer logs).",
    "frontend/src/components/CVEFeed.jsx": "Main CVE feed list — keyset pagination, stack relevance sort, scroll isolation (Track I).",
    "frontend/src/components/CVECard.jsx": "Single CVE feed card — renders API OP/Threat/KEV fields only (W2).",
    "frontend/src/components/SessionIdleWarning.jsx": "Warns before session idle lock; pairs with <code>useInactivityTimeout</code>.",
    "frontend/src/components/SessionLockOverlay.jsx": "Full-screen lock until re-auth after idle timeout.",
    "frontend/src/hooks/useInactivityTimeout.js": "Idle timer for session lock UX — respects analyst security settings.",
    "frontend/src/utils/displayPrefs.js": "Typography, motion, and poll-interval prefs — migrates legacy localStorage to <code>/api/me/preferences</code>.",
    "frontend/src/pages/admin/StoragePage.jsx": "Admin storage metrics, backup status, and DB explorer entry point.",
    "frontend/src/pages/admin/DisplayPage.jsx": "Instance typography defaults and analyst display settings admin surface.",
}

SEGMENT_META: list[tuple[str, str, str]] = [
    ("iv-comp-scheduler", "Scheduler jobs", "Every APScheduler <code>id=</code> registered in <code>scheduler.py</code>."),
    ("iv-comp-be-core", "Backend · core & infra", "Entrypoint, auth, HTTP client, rate limits, settings, logging."),
    ("iv-comp-be-db", "Backend · database", "All <code>backend/db/*.py</code> modules."),
    ("iv-comp-be-feeds", "Backend · feeds", "All <code>backend/feeds/*.py</code> ingest modules."),
    ("iv-comp-be-correlation", "Backend · correlation", "All <code>backend/correlation/*.py</code> modules."),
    ("iv-comp-be-scoring-detection", "Backend · scoring & detection", "Scoring, detection, matching, enrichment, brief."),
    ("iv-comp-be-routers", "Backend · routers", "All FastAPI router modules (analyst + admin)."),
    ("iv-comp-be-ai-ops", "Backend · AI, ML & operations", "AI/ML, webhooks, wallboard, backup, monitoring, onboarding."),
    ("iv-comp-be-misc", "Backend · other packages", "Security architecture, jobs, preferences, proof, migration, metrics."),
    ("iv-comp-fe-shell", "Frontend · analyst shell", "App shell, feed, BRIEF, IOC, Incidents, shared analyst components."),
    ("iv-comp-fe-drawer", "Frontend · DetailDrawer", "Drawer shell and tab components."),
    ("iv-comp-fe-forge", "Frontend · Forge & wallboard", "Forge navigator, wallboard, security posture UI."),
    ("iv-comp-fe-admin", "Frontend · admin console", "Admin pages and shared admin composites."),
    ("iv-comp-fe-ui", "Frontend · UI primitives", "<code>components/ui/</code> Radix-based primitives."),
    ("iv-comp-fe-utils", "Frontend · utils, hooks & context", "Shared hooks, contexts, scoring display helpers, utils."),
]

JOB_BLURBS: dict[str, str] = {
    "nvd_incremental_sync": "Incremental NVD 2.0 CVE ingest into <code>cves</code> with watermark; uses <code>resilient_client</code> + <code>api_queue</code>.",
    "kev_metadata_sync": "CISA KEV catalog sync into KEV deadline tables.",
    "epss_score_sync": "FIRST EPSS CSV ingest with Q5 identity skip on unchanged file hash.",
    "weekly_mitre_refresh": "MITRE ATT&amp;CK STIX + CVE→technique mapping refresh for Forge.",
    "kev_backlog_reconcile": "Detection backlog reconcile — emits <code>kev_backlog</code> notifications via <code>detection/backlog.py</code>.",
    "threatfox_sync": "ThreatFox bulk IOC mirror for corroboration lanes (CORR-PR-10).",
    "vulncheck_kev_sync": "VulnCheck community KEV catalog — no CISA KEV Threat floor.",
    "ioc_retro_match": "Retro-match IOC watchlist entries against newly ingested pulses.",
    "atlas_version_check": "MITRE ATLAS version drift check for Incidents/case studies feed.",
    "otx_nightly_correlation": "Nightly OTX pulse ingest pass feeding correlation engine input tables.",
    "otx_continuous_sync": "Registration-gated continuous OTX budget spend across the day.",
    "incident_feed_refresh": "Rebuild Incidents &amp; News RSS snapshot (five sources + case studies).",
    "exploit_sources_sync": "Orchestrates exploit feeds (ExploitDB, Metasploit, Nuclei, PoC-GitHub).",
    "embeddings_backfill": "pgvector embedding backfill for CVEs, techniques, campaigns (E1–E8).",
    "catchup_tick": "Catch-up mode nudger — embeddings, correlation, LLM extraction, CPE catalog.",
    "cpe_catalog_sync": "NVD CPE 2.3 dictionary → <code>software_catalog</code> (Q3).",
    "llm_product_extraction": "LLM extraction of affected products for unanalyzed CVEs; durable via Procrastinate when enabled.",
    "detection_context_sync": "Backfill <code>detection_ctx:{cve_id}</code> scaffold rows (default off).",
    "sigmahq_index_sync": "Weekly SigmaHQ tarball mirror into Postgres rule index.",
    "detection_context_llm": "Optional LLM artifact enrichment for DetectionContext (restart to register).",
    "nightly_correlation": "Correlation engine v2/v3 nightly run — Postgres only, no live OTX HTTP.",
    "vulnrichment_snapshot_sync": "CISA Vulnrichment SSVC/CVSS snapshot for <code>/risk</code> SSVC paths.",
    "cvelistv5_incremental_sync": "CVEList v5 incremental JSON sync — sibling to NVD modified feed.",
    "scheduled_backup": "Cron database backup to configured backup path.",
    "backup_deadman_check": "Alerts when scheduled backup is stale — webhook <code>backup_deadman</code> path.",
    "watchlist_monitor_alerts": "Pinned CVE KEV/EPSS/PoC change detection → <code>watchlist_alert</code> webhooks.",
    "api_key_health_check": "Lightweight provider key probes — separate from feed circuits.",
    "session_cleanup": "Purges expired sessions and refresh tokens.",
    "cache_retention_cleanup": "Retention sweep for caches, AI ops, webhook logs, dedupe claims (C3, #418).",
    "resource_metrics_sample": "RB-1 host resource utilization sample for admin Resources page.",
}


def module_docstring(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""
    key = str(path.relative_to(ROOT)).replace("\\", "/")
    if key in OVERRIDES:
        return OVERRIDES[key]
    if path.suffix == ".py":
        try:
            doc = ast.get_docstring(ast.parse(text)) or ""
            doc = " ".join(doc.strip().split())
            if doc:
                return doc[:450]
        except SyntaxError:
            pass
    m = re.search(r"/\*\*(.*?)\*/", text, re.DOTALL)
    if m:
        return " ".join(m.group(1).strip().split())[:450]
    return ""


def infer_blurb(path: Path) -> str:
    doc = module_docstring(path)
    if doc:
        return doc
    rel = str(path.relative_to(ROOT)).replace("\\", "/")
    name = path.stem
    return f"Product module <code>{rel}</code> (<code>{name}</code>)."


def collect_modules() -> list[dict]:
    items: list[dict] = []

    for py in sorted((ROOT / "backend").rglob("*.py")):
        rel = py.relative_to(ROOT)
        if any(p in SKIP_PARTS for p in rel.parts):
            continue
        if py.name == "__init__.py":
            continue
        key = str(rel).replace("\\", "/")
        items.append({"kind": "backend", "path": key, "blurb": infer_blurb(py)})

    src = ROOT / "frontend" / "src"
    for f in sorted(src.rglob("*")):
        if f.suffix not in {".jsx", ".js"}:
            continue
        rel = f.relative_to(ROOT)
        if ".test." in f.name or "node_modules" in rel.parts:
            continue
        key = str(rel).replace("\\", "/")
        kind = "frontend"
        if "/utils/" in key:
            kind = "util"
        elif "/hooks/" in key or "/context/" in key or "/scoring/" in key:
            kind = "hook"
        items.append({"kind": kind, "path": key, "blurb": infer_blurb(f)})

    sched = (ROOT / "backend/scheduler.py").read_text(encoding="utf-8")
    for jid in sorted(set(re.findall(r'\bid="([a-z0-9_]+)"', sched))):
        items.append({
            "kind": "job",
            "path": f"scheduler:{jid}",
            "blurb": JOB_BLURBS.get(jid, f"Scheduler job <code>{jid}</code> in <code>scheduler.py</code>."),
        })
    return items


def bucket(item: dict) -> str:
    kind = item["kind"]
    rel = item["path"]
    if kind == "job":
        return "iv-comp-scheduler"
    if kind == "backend":
        if rel.startswith("backend/db/"):
            return "iv-comp-be-db"
        if rel.startswith("backend/feeds/"):
            return "iv-comp-be-feeds"
        if rel.startswith("backend/correlation/"):
            return "iv-comp-be-correlation"
        if rel.startswith(("backend/scoring/", "backend/detection/", "backend/matching/", "backend/enrichment/", "backend/brief/")):
            return "iv-comp-be-scoring-detection"
        if rel.startswith("backend/routers/"):
            return "iv-comp-be-routers"
        if rel.startswith((
            "backend/ai/", "backend/ml/", "backend/webhooks/", "backend/wallboard/",
            "backend/backup/", "backend/monitoring/", "backend/notifications/",
            "backend/onboarding/", "backend/diagnostics/", "backend/services/",
        )):
            return "iv-comp-be-ai-ops"
        core = {
            "backend/main.py", "backend/scheduler.py", "backend/scheduler_locks.py",
            "backend/settings.py", "backend/operator_settings.py", "backend/config_schema.py",
            "backend/auth_middleware.py", "backend/dependencies.py", "backend/resilient_client.py",
            "backend/api_queue.py", "backend/api_queue_operations.py", "backend/api_metering.py",
            "backend/rate_limit.py", "backend/rate_limit_store.py", "backend/read_cache.py",
            "backend/redact.py", "backend/structured_logging.py", "backend/tracking.py",
            "backend/catchup_mode.py", "backend/database.py", "backend/destructive_actions.py",
            "backend/resource_collector.py", "backend/storage_metrics.py", "backend/settings_crypto.py",
            "backend/source_rate_limits.py", "backend/task_registry.py",
        }
        if rel in core or rel.startswith("backend/auth/"):
            return "iv-comp-be-core"
        return "iv-comp-be-misc"
    if "DetailDrawer" in rel:
        return "iv-comp-fe-drawer"
    if rel.endswith("Forge.jsx") or "WallboardPage" in rel or "security-architecture" in rel or "SecurityPosturePage" in rel:
        return "iv-comp-fe-forge"
    if "/pages/admin/" in rel or "/admin/shared/" in rel:
        return "iv-comp-fe-admin"
    if "/components/ui/" in rel:
        return "iv-comp-fe-ui"
    if kind in {"util", "hook"} or "/hooks/" in rel or "/context/" in rel or "/scoring/" in rel:
        return "iv-comp-fe-utils"
    return "iv-comp-fe-shell"


def py_repr(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)


def main() -> None:
    items = collect_modules()
    REGISTRY.write_text(json.dumps(items, indent=2), encoding="utf-8")

    buckets: dict[str, list[dict]] = {s[0]: [] for s in SEGMENT_META}
    for item in items:
        buckets[bucket(item)].append(item)

    lines = [
        '"""Per-component interview Q&A — generated from product source tree."""',
        "",
        "from __future__ import annotations",
        "",
        "COMPONENT_SEGMENTS: list[dict] = [",
    ]
    total_q = 0
    for slug, title, dek in SEGMENT_META:
        rows = sorted(buckets[slug], key=lambda x: x["path"])
        lines.append("    {")
        lines.append(f'        "slug": "{slug}",')
        lines.append(f'        "page_id": "{slug}",')
        lines.append('        "chapter_num": "Components",')
        lines.append(f'        "title": {py_repr(title)},')
        lines.append(f'        "dek": {py_repr(dek)},')
        lines.append('        "questions": [')
        for row in rows:
            if row["kind"] == "job":
                jid = row["path"].split(":", 1)[1]
                q = f"What does scheduler job `{jid}` do?"
            else:
                q = f"What does `{row['path']}` do?"
            a = row["blurb"]
            lines.append(
                f'            {{"category": "overview", "q": {py_repr(q)}, "a": {py_repr(a)}}},'
            )
            total_q += 1
        lines.append("        ],")
        lines.append("    },")
    lines.append("]")
    lines.append("")
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"registry: {len(items)} components")
    print(f"wrote {OUT.name}: {total_q} questions in {len(SEGMENT_META)} pages")


if __name__ == "__main__":
    main()
