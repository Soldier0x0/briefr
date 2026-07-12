#!/usr/bin/env python3
"""Generate ./architecture-map.html — self-contained BRIEFR architecture map."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "architecture-map.html"

DEAD_SUB = "DEAD — zero callers confirmed"

clusters = [
    {"id": "external", "label": "External Feeds", "x": 16, "y": 24, "w": 218, "h": 1180},
    {"id": "scheduler", "label": "Scheduler", "x": 250, "y": 24, "w": 218, "h": 1180},
    {"id": "sqlite", "label": "SQLite DB", "x": 484, "y": 24, "w": 196, "h": 1180},
    {"id": "fastapi", "label": "FastAPI", "x": 696, "y": 24, "w": 268, "h": 1180},
    {"id": "react-shell", "label": "React Shell", "x": 980, "y": 24, "w": 210, "h": 1180},
    {"id": "feed-brief", "label": "Feed / Brief UI", "x": 1206, "y": 24, "w": 210, "h": 1180},
    {"id": "detail-tools", "label": "Detail / Tools UI", "x": 1432, "y": 24, "w": 228, "h": 1180},
]

CLUSTER_COLORS = {
    "external": "external",
    "scheduler": "accent",
    "sqlite": "db",
    "fastapi": "route",
    "react-shell": "client",
    "feed-brief": "service",
    "detail-tools": "service",
}


def N(
    id_,
    cluster,
    label,
    sub,
    x,
    y,
    w=188,
    h=36,
    color="service",
    *,
    role,
    plain,
    path,
    notes,
    tag,
    critical=False,
    extra=None,
):
    o = {
        "id": id_,
        "cluster": cluster,
        "label": label,
        "sub": sub,
        "x": x,
        "y": y,
        "w": w,
        "h": h,
        "color": color,
        "role": role,
        "plain": plain,
        "path": path,
        "notes": notes,
        "tag": tag + (["all"] if "all" not in tag else []),
    }
    if critical:
        o["critical"] = True
    if extra:
        o.update(extra)
    return o


def col_x(cluster: str) -> int:
    return next(c["x"] for c in clusters if c["id"] == cluster) + 14


def y(row: float, step: float = 44.0) -> int:
    return int(52 + row * step)


nodes: list[dict] = []

# ── External Feeds ──────────────────────────────────────────
ext = [
    ("ext-nvd", "NVD API 2.0", "services.nvd.nist.gov", "backend/feeds/nvd.py:198", "NVD REST 2.0 paginated CVE fetch via resilient_get.", "United States national vulnerability database.", ["line:198 — _fetch_page() with 429 retry", "line:180 — NVD_API_KEY optional; no-key rate 50 req/30s"], ["overview", "scheduler"]),
    ("ext-kev", "CISA KEV JSON", "known_exploited_vulnerabilities.json", "backend/feeds/kev.py:46", "fetch_kev() downloads CISA Known Exploited Vulnerabilities catalog.", "Catalog of vulnerabilities actively exploited in the wild.", ["line:46 — parse_kev_catalog() normalizes vendor/due dates"], ["scheduler"]),
    ("ext-epss", "FIRST EPSS CSV", "epss.cyentia.com", "backend/feeds/epss.py:132", "fetch_epss() bulk EPSS probability scores.", "Exploit prediction scores for prioritization.", ["line:132 — CSV bulk + API batch fallback"], ["scheduler"]),
    ("ext-mitre-stix", "MITRE ATT&CK STIX", "attack.mitre.org", "backend/feeds/mitre.py:394", "download_enterprise_attack() STIX bundle for techniques/groups.", "MITRE attack technique definitions.", ["line:457 — refresh_mitre_data() upserts mitre_techniques"], ["scheduler"]),
    ("ext-atlas-yaml", "MITRE ATLAS YAML", "atlas.mitre.org", "backend/feeds/atlas.py:185", "download_atlas_bundle() AI/ML threat matrix.", "AI system attack techniques and case studies.", ["line:210 — refresh_atlas_data()"], ["scheduler", "incidents"]),
    ("ext-otx", "AlienVault OTX", "otx.alienvault.com", "backend/feeds/otx.py:24", "OTX pulse/IOC API for campaign correlation.", "Open threat exchange pulses linking CVEs to campaigns.", ["line:366 — run_otx_nightly_correlation() batch job"], ["cve-detail", "ioc", "correlation", "scheduler"]),
    ("ext-sploitus", "Sploitus", "sploitus.com", "backend/feeds/extended.py:101", "fetch_sploitus_exploits() on-demand PoC search.", "Public exploit aggregator for proof-of-concept code.", ["line:497 — feed_cache key sploitus:{cve_id}"], ["cve-detail"]),
    ("ext-greynoise", "GreyNoise", "api.greynoise.io", "backend/feeds/extended.py:186", "fetch_greynoise_ip() IP scanning context.", "Internet-wide scan/noise intelligence for IPs.", ["line:689 — greynoise_for_ip is live; lookup_greynoise alias dead"], ["cve-detail", "ioc"]),
    ("ext-osv", "OSV.dev", "api.osv.dev", "backend/feeds/osv.py:20", "fetch_osv_by_cve() package-level vuln data.", "Open source package vulnerability records.", ["line:107 — called serially from get_cve"], ["cve-detail"]),
    ("ext-circl", "CIRCL CVE", "cve.circl.lu", "backend/feeds/extended.py:419", "fetch_circl_cve() CAPEC/enrichment overlay.", "Luxembourg CERT CVE enrichment API.", ["line:575 — enrich_cve_circl second DB connection"], ["cve-detail"]),
    ("ext-mb", "MalwareBazaar", "bazaar.abuse.ch", "backend/feeds/extended.py:236", "fetch_malwarebazaar_hash() IOC hash lookup.", "Malware sample hash intelligence.", ["line:652 — lookup_malwarebazaar from enrichment/ioc"], ["ioc"]),
    ("ext-urlhaus", "URLhaus", "urlhaus.abuse.ch", "backend/feeds/extended.py:292", "fetch_urlhaus_indicator() URL IOC lookup.", "Malicious URL feed from abuse.ch.", ["line:667 — lookup_urlhaus"], ["ioc"]),
    ("ext-abuseipdb", "AbuseIPDB", "api.abuseipdb.com", "backend/enrichment/ioc.py:123", "_lookup_abuseipdb() IP reputation.", "IP abuse reports for IOC triage.", ["line:212 — lookup_ioc orchestrates"], ["ioc"]),
    ("ext-vt", "VirusTotal", "virustotal.com", "backend/enrichment/ioc.py:114", "_lookup_vt_ip/hash/domain VT v3 API.", "Multi-engine malware/IP/domain reputation.", ["line:74 — _quota_safe_get respects quotas"], ["ioc"]),
    ("ext-github", "GitHub API", "api.github.com", "backend/feeds/cvelistv5.py:53", "cvelistV5 + Vulnrichment via GitHub compare/tree.", "CVE JSON v5 and CISA enrichment repos.", ["line:184 — fetch_cvelistv5_delta incremental"], ["scheduler"]),
    ("ext-rss", "5 RSS Feeds", "INCIDENT_RSS_SOURCES", "backend/feeds/incident_sources.py:3", "Five security news RSS/Atom feeds for Incidents tab.", "Headline feeds (Hacker News, Krebs, etc.).", ["line:3 — five sources in INCIDENT_RSS_SOURCES", "line:218 — fetch_all_incident_news_parallel"], ["incidents", "scheduler"]),
    ("ext-groq", "Groq API", "api.groq.com", "backend/ai/summary.py:244", "_call_groq() primary LLM for PDF executive summary.", "Fast LLM for optional report summaries.", ["line:311 — generate_executive_summary chain"], ["pdf"]),
    ("ext-anthropic", "Anthropic API", "api.anthropic.com", "backend/ai/summary.py:278", "_call_anthropic() fallback when Groq fails.", "Backup language model for PDF summaries.", ["line:22 — claude-haiku-4-5 model"], ["pdf"]),
]
for i, (id_, label, sub, path, role, plain, notes, tags) in enumerate(ext):
    nodes.append(
        N(
            id_,
            "external",
            label,
            sub,
            col_x("external"),
            y(i),
            color="external",
            role=role,
            plain=plain,
            path=path,
            notes=notes,
            tag=tags,
            critical=(id_ == "ext-nvd"),
        )
    )

# ── Scheduler jobs ─────────────────────────────────────────
jobs = [
    ("job-nvd-sync", "nvd_incremental_sync", "Interval · 1 h · CRITICAL", "backend/scheduler.py:146", "run_nvd_incremental_sync() polls NVD watermark and upserts CVEs.", "Hourly check for new national-database vulnerabilities.", ["line:146 — _nvd_lock prevents overlap", "line:181 — calls fetch_nvd_cve_updates()"], True, ["overview", "scheduler"]),
    ("job-kev", "kev_metadata_sync", "Interval · KEV minutes", "backend/scheduler.py:258", "run_kev_sync() refreshes KEV flags and kev_deadlines.", "Keeps exploited-in-the-wild flags current.", ["line:258 — asyncio lock _kev_lock"], False, ["scheduler"]),
    ("job-epss", "epss_score_sync", "Interval · EPSS hours", "backend/scheduler.py:356", "run_epss_sync() updates EPSS scores on CVE rows.", "Refreshes exploit probability scores.", ["line:405 — run_epss_backfill startup one-shot"], False, ["scheduler"]),
    ("job-mitre", "weekly_mitre_refresh", "Cron Sun 02:00", "backend/scheduler.py:513", "run_weekly_mitre_refresh() ATT&CK + groups STIX.", "Weekly MITRE technique/group refresh.", ["line:553 — maybe_run_mitre_on_startup if empty"], False, ["scheduler"]),
    ("job-otx", "otx_nightly_correlation", "Cron nightly IST", "backend/scheduler.py:777", "run_otx_nightly_sync() OTX pulse IOC cache.", "Nightly AlienVault campaign correlation ingest.", ["line:366 — feeds/otx.run_otx_nightly_correlation"], False, ["correlation", "scheduler"]),
    ("job-incident", "incident_feed_refresh", "Interval · 30 min", "backend/scheduler.py:725", "run_incident_feed_refresh() RSS snapshot warm.", "Refreshes Incidents tab news snapshot.", ["line:952 — skipped when PLAYWRIGHT_SMOKE=1"], False, ["incidents", "scheduler"]),
    ("job-exploit", "exploit_sources_sync", "Interval · exploit hours", "backend/scheduler.py:607", "run_exploit_sources_sync() ExploitDB/Nuclei/Metasploit.", "Syncs public exploit source indexes.", ["line:22 — exploit_sources_enabled() gate"], False, ["scheduler"]),
    ("job-embeddings", "embeddings_backfill", "GATED · 6 h", "backend/scheduler.py:805", "run_embeddings_sync() — no-op unless EMBEDDINGS_ENABLED=1.", "Optional semantic embedding backfill.", ["line:988 — env gate in ml/embeddings.py:69", "GATED (EMBEDDINGS_ENABLED)"], False, ["scheduler"]),
    ("job-llm-prod", "llm_product_extraction", "GATED · 6 h", "backend/scheduler.py:838", "run_llm_extraction_sync() LLM CPE extraction.", "Optional LLM product parsing for unanalyzed CVEs.", ["line:993 — LLM_PRODUCT_EXTRACTION_ENABLED"], False, ["scheduler"]),
    ("job-correlation", "nightly_correlation", "Cron 01:00 IST", "backend/scheduler.py:740", "run_nightly_correlation() three-level engine.", "Nightly infrastructure/actor/temporal correlation.", ["line:416 — correlation/engine.run_nightly_correlation"], False, ["correlation", "scheduler"]),
    ("job-vulnrich", "vulnrichment_snapshot_sync", "Interval · hours", "backend/scheduler.py:644", "run_vulnrichment_sync() CISA ADP GitHub snapshot.", "Bulk CISA vulnrichment enrichment ingest.", ["line:141 — fetch_vulnrichment_for_cve is DEAD"], False, ["scheduler"]),
    ("job-cvelist", "cvelistv5_incremental_sync", "Interval · minutes", "backend/scheduler.py:680", "run_cvelistv5_sync() CVE JSON v5 delta.", "Incremental CVE List v5 record merge.", ["line:184 — fetch_cvelistv5_delta"], False, ["scheduler"]),
    ("job-backup", "backup_deadman_check", "Interval · backup/2", "backend/scheduler.py:872", "run_backup_deadman_check() WAL backup + webhook.", "Periodic encrypted DB backup and dead-man alert.", ["line:872 — calls backup.manager.run_backup"], False, ["backup", "scheduler"]),
    ("job-startup", "maybe_run_on_startup", "One-shot · boot", "backend/scheduler.py:574", "maybe_run_on_startup() EPSS backfill + bootstrap ingest.", "First-boot full ingest when fewer than 10 CVE rows.", ["line:574 — full ingest if cve count < 10"], False, ["overview", "scheduler"]),
]
for i, (id_, label, sub, path, role, plain, notes, crit, tags) in enumerate(jobs):
    sub_final = sub
    if "GATED" in notes[-1]:
        sub_final = notes[-1]
    nodes.append(
        N(
            id_,
            "scheduler",
            label,
            sub_final,
            col_x("scheduler"),
            y(i),
            color="accent" if id_ != "job-nvd-sync" else "service",
            role=role,
            plain=plain,
            path=path,
            notes=[n for n in notes if not n.startswith("GATED")],
            tag=tags,
            critical=crit,
        )
    )

# ── SQLite table groups ────────────────────────────────────
dbs = [
    ("db-cves", "cves", "26-col CVE core table", "backend/database.py:22", "Primary CVE rows: scores, KEV, EPSS, products, summary.", "Main vulnerability inventory the UI lists.", ["line:716 — upsert_cves() merge on cve_id", "line:18 — init_db() inline migrations ~2400 lines"], ["overview", "scheduler"]),
    ("db-kev", "kev_deadlines", "CISA due dates", "backend/database.py:57", "KEV deadline metadata joined in get_cve/list.", "Federal remediation due dates for KEV items.", ["line:57 — date_added, due_date, ransomware flag"], ["scheduler", "brief"]),
    ("db-epss-hist", "epss_history", "EPSS sparkline history", "backend/database.py:150", "Time series EPSS scores per CVE.", "Historical exploit probability for trend charts.", ["line:728 — GET /api/cves/{id}/epss-history"], ["cve-detail", "brief"]),
    ("db-mitre", "mitre_*", "techniques + groups + maps", "backend/database.py:91", "mitre_techniques, mitre_groups, cve_technique_map, group_technique_map.", "MITRE ATT&CK technique and group mappings.", ["line:91 — mitre_techniques STIX ingest target"], ["forge", "correlation"]),
    ("db-atlas", "atlas_*", "AI threat matrix", "backend/database.py:113", "atlas_techniques, atlas_case_studies, cve_atlas_map.", "MITRE ATLAS AI attack techniques and studies.", ["line:113 — atlas_techniques table"], ["incidents", "cve-detail"]),
    ("db-otx", "otx_*", "pulse + IOC cache", "backend/database.py:201", "otx_cve_pulses, otx_pulse_iocs for campaign links.", "Stored OTX campaign pulses and indicators.", ["line:201 — populated by nightly OTX job"], ["correlation", "cve-detail"]),
    ("db-corr", "correlation_*", "3-level correlation", "backend/database.py:233", "correlation_actor, correlation_temporal.", "Precomputed CVE correlation results.", ["line:416 — engine.run_nightly_correlation writes"], ["correlation"]),
    ("db-cache", "feed_cache / ioc_cache", "Two cache strategies", "backend/database.py:48", "feed_cache snapshot keys vs ioc_cache 6 h TTL.", "Caches expensive external lookups locally.", ["line:1384 — ioc_cache 6 h TTL", "line:1407 — feed_cache per-key max_age_hours"], ["ioc", "cve-detail"]),
    ("db-watchlist", "watchlist", "pin · legacy snooze", "backend/database.py:330", "watchlist state; UI pin-only, snooze API retained.", "Analyst pinned CVEs for the feed filter.", ["line:330 — state CHECK pin|snooze"], ["overview"]),
    ("db-hunt", "hunt_packs", "Forge detection packs", "backend/database.py:297", "Generated Sigma/SIEM hunt pack content.", "Stored detection engineering packs per technique.", ["line:359 — GET /api/hunt-packs/{technique_id}"], ["forge"]),
    ("db-usage", "api_usage / audit_log", "quota + audit trail", "backend/database.py:74", "api_usage counters and audit_log actions.", "Tracks external API usage and admin actions.", ["line:317 — audit_log for backup/restore"], ["ioc"]),
    ("db-exploits", "cve_exploits", "ExploitDB/Nuclei/MS", "backend/database.py:160", "Normalized exploit source rows per CVE.", "Public exploit metadata from batch sync.", ["line:607 — exploit_sources_sync populates"], ["scheduler"]),
    ("db-embeddings", "cve_embeddings", "GATED vectors", "backend/database.py:286", "Semantic embeddings when EMBEDDINGS_ENABLED=1.", "Optional vector store for semantic search.", ["line:286 — only written when ML enabled", "GATED (EMBEDDINGS_ENABLED)"], ["scheduler"]),
]
for i, (id_, label, sub, path, role, plain, notes, tags) in enumerate(dbs):
    sub_f = sub
    if notes and notes[-1].startswith("GATED"):
        sub_f = notes[-1]
    nodes.append(
        N(
            id_,
            "sqlite",
            label,
            sub_f,
            col_x("sqlite"),
            y(i),
            w=168,
            color="db",
            role=role,
            plain=plain,
            path=path,
            notes=[n for n in notes if not n.startswith("GATED")],
            tag=tags,
            critical=(id_ == "db-cves"),
        )
    )

# ── FastAPI layer ──────────────────────────────────────────
api_y = 0

def api_node(id_, label, sub, path, role, plain, notes, tags, crit=False, dead=False):
    global api_y
    n = N(
        id_,
        "fastapi",
        label,
        f"{sub} · {DEAD_SUB}" if dead else sub,
        col_x("fastapi"),
        y(api_y),
        w=240,
        color="route" if "router" in id_ else "service",
        role=role,
        plain=plain,
        path=path,
        notes=notes,
        tag=tags,
        critical=crit,
    )
    api_y += 1
    nodes.append(n)

api_node("main-py", "main.py", "lifespan · middleware", "backend/main.py:42", "FastAPI app: load_dotenv(), init_db(), start_scheduler(), router mounts.", "Application entry that wires HTTP API and startup jobs.", ["line:11 — load_dotenv() without override", "line:172 — include_router sequence snapshot-tested"], ["overview", "all"])
api_node("router-cves", "routers/cves.py", "GET /api/cves · detail", "backend/routers/cves.py:509", "list_cves() paginated feed; get_cve() detail enrichment chain.", "Main CVE list and detail HTTP handlers.", ["line:509 — list_cves DB-only (fast)", "line:800 — get_cve serial Sploitus→GN→OTX→OSV→CIRCL"], ["overview", "cve-detail", "asset-match"], crit=True)
api_node("router-ioc", "routers/ioc.py", "POST /api/ioc/lookup", "backend/routers/ioc.py:75", "IOC lookup endpoint with rate_limit_ioc dependency.", "Analyst IOC triage API.", ["line:75 — Depends(rate_limit_ioc)"], ["ioc"])
api_node("router-refresh", "routers/refresh.py", "POST /api/refresh*", "backend/routers/refresh.py:37", "Manual ingest triggers (NVD/KEV/EPSS/MITRE).", "On-demand data refresh buttons.", ["line:37 — rate limited refresh endpoints"], ["scheduler"])
api_node("router-brief", "routers/brief.py", "GET /api/brief", "backend/routers/brief.py:11", "Morning brief JSON from build_morning_brief().", "Unified priority queue for the Brief tab.", ["line:11 — read-path only, no ingest"], ["brief"])
api_node("router-forge", "routers/forge.py", "Forge + hunt packs", "backend/routers/forge.py:103", "GET /api/forge/coverage and hunt pack CRUD.", "Detection engineering coverage map API.", ["line:103 — forge_coverage stack filter"], ["forge"])
api_node("router-atlas", "routers/atlas.py", "ATLAS + case studies", "backend/routers/atlas.py:45", "GET /api/case-studies/feed combined RSS+ATLAS.", "Incidents tab feed endpoint.", ["line:45 — case_study_feed.get_incident_feed"], ["incidents"])
api_node("router-health", "routers/health.py", "GET /api/health", "backend/routers/health.py:48", "Health + circuit breaker status from resilient_client.", "Backend health and upstream source status.", ["line:48 — exposes per-source circuit state"], ["all"])
api_node("router-stats", "stats (cves.py)", "GET /api/stats*", "backend/routers/cves.py:169", "stats + stats_timeline for dashboard counters.", "Aggregate CVE statistics for Brief charts.", ["line:169 — GET /api/stats", "line:211 — GET /api/stats/timeline"], ["brief"])
api_node("router-ai", "ai (meta.py)", "POST /api/ai/summary", "backend/routers/meta.py:133", "ai_summary() → generate_executive_summary chain.", "PDF executive summary generation API.", ["line:133 — POST body AiSummaryRequest"], ["pdf"])
api_node("router-config", "routers/config.py", "GET /api/config/risk", "backend/routers/config.py:26", "Serves v1.1b weight constants for UI formula display.", "Risk score weight configuration endpoint.", ["line:26 — weights from scoring/risk.py constants"], ["asset-match"])
api_node("router-meta", "routers/meta.py", "version · usage · watchlist", "backend/routers/meta.py:66", "Version, IOC usage quota, investigation summary routes.", "Misc metadata and usage endpoints.", ["line:108 — GET /api/usage/ioc quota header"], ["ioc"])
api_node("router-watchlist", "routers/watchlist.py", "GET/POST /api/watchlist", "backend/routers/watchlist.py:63", "Pin/snooze watchlist CRUD (UI pin-only).", "Persist analyst watchlist state.", ["line:99 — DELETE snoozes legacy cleanup"], ["overview"])
api_node("svc-resilient", "resilient_client.py", "httpx pool · circuits", "backend/resilient_client.py:45", "Shared httpx.AsyncClient with per-source circuit breakers.", "Central outbound HTTP with failure protection.", ["line:27 — CIRCUIT_COOLDOWN_SECONDS default 60", "line:45 — singleton AsyncClient pool"], ["scheduler", "all"])
api_node("svc-rate-limit", "rate_limit.py", "token bucket", "backend/rate_limit.py:1", "In-memory rate limits for IOC lookup and refresh POSTs.", "Prevents quota burn and ingest stampede.", ["line:3 — POST /api/ioc/lookup protected", "line:5 — single uvicorn worker assumption"], ["ioc"])
api_node("svc-correlation", "correlation/engine.py", "3-level nightly", "backend/correlation/engine.py:416", "run_nightly_correlation() infrastructure/actor/temporal.", "Batch correlation engine writing correlation_* tables.", ["line:20 — CACHE_HOURS = 6", "line:72 — find_shared_infrastructure uses OTX IOCs"], ["correlation"])
api_node("svc-brief", "brief/service.py", "build_morning_brief()", "backend/brief/service.py:54", "Server-side brief queue: KEV due, EPSS movers, stack match.", "Computes the morning priority CVE list.", ["line:54 — stack profile hash for reasons"], ["brief"])
api_node("svc-enrich-ioc", "enrichment/ioc.py", "lookup_ioc()", "backend/enrichment/ioc.py:212", "Multi-source IOC orchestration with ioc_cache.", "Parallel VT/AbuseIPDB/GN/MB/URLhaus/OTX lookup.", ["line:212 — cache via get_ioc_cache 6 h"], ["ioc"])
api_node("svc-ai", "ai/summary.py", "Groq→Anthropic→template", "backend/ai/summary.py:311", "generate_executive_summary() LLM chain for PDF export.", "Optional AI-written executive summary paragraph.", ["line:311 — explicit PDF export only"], ["pdf"])
api_node("svc-backup", "backup/manager.py", "WAL-safe · age encrypt", "backend/backup/manager.py:1", "run_backup() sqlite backup + optional age encryption.", "Encrypted database archive and restore on boot.", ["line:4 — sqlite3.Connection.backup() WAL-safe", "line:44 — DEFAULT_AGE_KEY_FILE outside BACKUP_DIR"], ["backup"])
api_node("svc-scoring", "scoring/risk.py", "calculate_risk_score()", "backend/scoring/risk.py:405", "Canonical Risk Score v1.1b + calculate_momentum().", "Server-side explainable priority score.", ["line:405 — calculate_risk_score() canonical", "line:473 — calculate_momentum()"], ["cve-detail", "asset-match"])
api_node("svc-asset-match", "scoring/asset_match.py", "resolve_asset_component()", "backend/scoring/asset_match.py:203", "CPE match + fuzzy graduation for asset component.", "Maps analyst profile to asset exposure tier.", ["line:203 — CPE first, fuzzy fallback"], ["asset-match", "cve-detail"])
api_node("svc-nvd-feed", "feeds/nvd.py", "fetch_nvd_cve_updates()", "backend/feeds/nvd.py:398", "Incremental NVD delta fetch with watermark overlap.", "Core NVD ingest function for scheduler job.", ["line:398 — watermark + overlap_minutes", "line:198 — 429 retry in _fetch_page"], ["overview", "scheduler"], crit=True)
api_node("svc-upsert", "database.py", "upsert_cves()", "backend/database.py:716", "Bulk merge CVE dicts into cves table.", "Writes ingested CVE records to SQLite.", ["line:716 — ON CONFLICT DO UPDATE merge"], ["overview", "scheduler"], crit=True)
api_node("svc-webhooks", "webhooks/alerts.py", "Discord/Telegram alerts", "backend/webhooks/alerts.py:92", "KEV stack + backup dead-man webhook dispatch.", "Outbound alert notifications (no HTTP router).", ["line:92 — check_new_kev_alerts after KEV sync", "line:136 — backup dead-man alert"], ["backup"])
api_node("svc-case-feed", "feeds/case_study_feed.py", "incident snapshot", "backend/feeds/case_study_feed.py:177", "get_incident_feed() RSS+ATLAS snapshot reader.", "Serves cached Incidents tab cards.", ["line:22 — default 30 min refresh interval"], ["incidents"])
api_node("dead-plain-summary", "build_plain_summary", DEAD_SUB, "backend/enrichment/cve.py:93", "build_plain_summary() — zero production callers.", "Orphaned plain-English summary helper.", ["line:93 — only defined, never imported"], ["cve-detail"])
api_node("dead-vulnrichment", "fetch_vulnrichment_for_cve", DEAD_SUB, "backend/feeds/vulnrichment.py:141", "Per-CVE vulnrichment fetch — unused; bulk sync used.", "Dead on-demand vulnrichment helper.", ["line:104 — fetch_vulnrichment_enrichments is live path"], ["scheduler"], dead=True)
api_node("dead-gn-alias", "lookup_greynoise", DEAD_SUB, "backend/feeds/extended.py:685", "Alias wrapper — greynoise_for_ip is canonical.", "Unused GreyNoise lookup alias.", ["line:689 — greynoise_for_ip used by get_cve"], ["cve-detail"], dead=True)
api_node("svc-matching", "matching/cpe.py", "score_cve_for_assets()", "backend/matching/cpe.py:124", "CPE version-range matching for POST /api/cves/match.", "Matches asset inventory to CVE affected products.", ["line:124 — score_cve_for_assets best match"], ["asset-match"])
api_node("ml-embeddings", "ml/embeddings.py", "GATED (EMBEDDINGS_ENABLED)", "backend/ml/embeddings.py:69", "fastembed CPU embeddings when EMBEDDINGS_ENABLED=1.", "Optional semantic embedding pipeline.", ["line:69 — embeddings_enabled() env gate", "line:805 — scheduler job no-op by default"], ["scheduler"])

# ── React Shell ────────────────────────────────────────────
shell = [
    ("fe-main", "main.jsx", "React root + fonts", "frontend/src/main.jsx:24", "ReactDOM root, AssetProfileProvider, fetchAndCacheRiskWeights().", "Browser entry point and risk-weight prefetch.", ["line:22 — fetchAndCacheRiskWeights().catch", "line:27 — AssetProfileProvider wraps App"], ["overview", "asset-match"]),
    ("fe-app", "App.jsx", "tab shell · drawer host", "frontend/src/App.jsx:235", "Tab panels (hidden not unmounted), drawer controller, keyboard shortcuts.", "Main application layout and global state.", ["line:35 — lazy BriefCharts import", "line:31 — createCveDrawerController"], ["overview", "all"]),
    ("fe-api", "api.js", "fetch* · 20 s timeout", "frontend/src/api.js:52", "fetchCVEs() and all /api client wrappers with AbortSignal.timeout.", "Frontend HTTP client for the backend API.", ["line:2 — REQUEST_TIMEOUT_MS = 20000", "line:6 — AbortSignal.timeout on every request"], ["overview", "all"], True),
    ("fe-asset-ctx", "AssetProfileContext.jsx", "profile · inactivity lock", "frontend/src/context/AssetProfileContext.jsx:18", "Asset profile state; useInactivityTimeout for session lock.", "Local asset inventory for stack matching.", ["line:13 — useInactivityTimeout imported (live)", "line:78 — fetchCveAssetMatch on profile save"], ["asset-match"]),
    ("fe-inv-ctx", "InvestigationContext.jsx", "investigation thread", "frontend/src/context/InvestigationContext.jsx:53", "Cross-tab investigation pivot state.", "Tracks analyst investigation pivots across tabs.", ["line:53 — InvestigationProvider"], ["pdf", "ioc"]),
    ("fe-risk", "riskScore.js", "UI helpers · weights", "frontend/src/scoring/riskScore.js:47", "riskScoreColor(), buildRiskHeroSummary(); fetchAndCacheRiskWeights for formula display.", "Presentation helpers for server-computed scores.", ["line:47 — fetchAndCacheRiskWeights from /api/config/risk", "line:61 — buildRiskHeroSummary only; no score math"], ["asset-match", "cve-detail"]),
    ("fe-drawer-ctrl", "openCveDrawer.js", "createCveDrawerController", "frontend/src/utils/openCveDrawer.js:5", "Drawer open flow: fetchCVE + loading state.", "Opens CVE detail drawer from card click.", ["line:5 — fetchCVE then setSelectedCVE"], ["overview", "cve-detail"]),
]
for i, row in enumerate(shell):
    crit = len(row) > 8 and row[8]
    tags = row[7]
    nodes.append(
        N(
            row[0],
            "react-shell",
            row[1],
            row[2],
            col_x("react-shell"),
            y(i),
            color="client",
            role=row[4],
            plain=row[5],
            path=row[3],
            notes=row[6],
            tag=tags,
            critical=crit or row[0] == "fe-api",
        )
    )

# ── Feed / Brief UI ────────────────────────────────────────
feed_ui = [
    ("ui-cve-feed", "CVEFeed.jsx", "loadPage · infinite scroll", "frontend/src/components/CVEFeed.jsx:151", "loadPage() calls fetchCVEs for paginated feed.", "Main vulnerability feed the analyst sees first.", ["line:151 — loadPage useCallback", "line:37 — export default CVEFeed"], ["overview"], True),
    ("ui-cve-card", "CVECard.jsx", "card render · drawer open", "frontend/src/components/CVECard.jsx:48", "Renders each CVE row; click opens drawer.", "Individual vulnerability card in the feed.", ["line:48 — export default CVECard", "line:48 — risk score + momentum arrow"], ["overview"], True),
    ("ui-filter", "FilterBar.jsx", "filters · stack · KEV", "frontend/src/components/FilterBar.jsx:60", "Filter chips passed as fetchCVEs query params.", "Feed filter controls (severity, KEV, PoC, etc.).", ["line:60 — export default FilterBar"], ["overview"]),
    ("ui-brief", "MorningBrief.jsx", "GET /api/brief", "frontend/src/components/MorningBrief.jsx:92", "Morning brief tab consuming /api/brief JSON.", "Priority CVE queue for the Brief tab.", ["line:92 — export default MorningBrief"], ["brief"]),
    ("ui-stats", "StatsRow.jsx", "GET /api/stats", "frontend/src/components/StatsRow.jsx:20", "Dashboard stat tiles from fetchStats.", "Headline counters on Brief dashboard.", ["line:20 — export default StatsRow"], ["brief"]),
    ("ui-heatmap", "TimelineHeatmap.jsx", "timeline heatmap", "frontend/src/components/TimelineHeatmap.jsx:36", "CVE publication heatmap from fetchStatsTimeline.", "Calendar heatmap of CVE volume.", ["line:36 — export default TimelineHeatmap"], ["brief"]),
    ("ui-charts", "BriefCharts.jsx", "Chart.js lazy", "frontend/src/components/BriefCharts.jsx:306", "Lazy-loaded brief charts (severity, KEV, etc.).", "Visual charts on the Brief tab.", ["line:306 — export default BriefCharts"], ["brief"]),
    ("ui-changed", "WhatChangedPanel.jsx", "GET /api/changes", "frontend/src/components/WhatChangedPanel.jsx:65", "Recent field changes panel.", "Shows what changed recently in the feed.", ["line:65 — export default WhatChangedPanel"], ["brief"]),
    ("ui-hero", "Hero.jsx", "landing hero", "frontend/src/components/Hero.jsx:3", "Hero banner on Brief tab.", "Welcome header on the brief landing.", ["line:3 — export default Hero"], ["brief"]),
    ("ui-sidebar", "Sidebar.jsx", "filter sidebar", "frontend/src/components/Sidebar.jsx:59", "Left sidebar filter stack on Feed tab.", "Secondary filter sidebar on feed.", ["line:59 — export default Sidebar"], ["overview"]),
    ("ui-case", "CaseStudies.jsx", "Incidents tab", "frontend/src/components/CaseStudies.jsx:69", "fetchCaseStudyFeed() RSS+ATLAS cards.", "Security news and ATLAS incident cards.", ["line:69 — export default CaseStudies"], ["incidents"]),
]
for i, row in enumerate(feed_ui):
    nodes.append(
        N(
            row[0],
            "feed-brief",
            row[1],
            row[2],
            col_x("feed-brief"),
            y(i),
            color="service",
            role=row[4],
            plain=row[5],
            path=row[3],
            notes=row[6],
            tag=row[7],
            critical=row[8] if len(row) > 8 else False,
        )
    )

# ── Detail / Tools UI ──────────────────────────────────────
detail_ui = [
    ("ui-drawer", "DetailDrawer.jsx", "detail · PDF export", "frontend/src/components/DetailDrawer.jsx:1070", "CVE detail drawer; fetchCVERisk() for canonical score.", "Full vulnerability detail panel.", ["line:1070 — export default DetailDrawer", "line:1100 — fetchCVERisk on profile/cve change"], ["cve-detail", "pdf"]),
    ("ui-atlas-sect", "DrawerAtlasSection.jsx", "ATLAS in drawer", "frontend/src/components/DrawerAtlasSection.jsx:10", "ATLAS techniques/case studies section in drawer.", "AI threat context inside CVE detail.", ["line:10 — export default DrawerAtlasSection"], ["cve-detail"]),
    ("ui-ioc", "IOCLookup.jsx", "POST /api/ioc/lookup", "frontend/src/components/IOCLookup.jsx:734", "IOC lookup tab with quota header.", "Indicator lookup tool for analysts.", ["line:734 — export default IOCLookup"], ["ioc"]),
    ("ui-forge", "Forge.jsx", "Forge tab", "frontend/src/components/Forge.jsx:280", "fetchForgeCoverage + fetchHuntPack UI.", "Detection engineering coverage workspace.", ["line:280 — export default Forge"], ["forge"]),
    ("ui-watchlist", "useWatchlist.js", "pin · legacy snooze clear", "frontend/src/hooks/useWatchlist.js:12", "Watchlist hook; clears legacy snooze on boot.", "Pin state synced with /api/watchlist.", ["line:12 — export function useWatchlist", "line:12 — pin-only UI, snooze API retained"], ["overview"]),
    ("ui-pdf", "pdfReport.js", "jsPDF export", "frontend/src/utils/pdfReport.js:381", "downloadSingleCvePdf() browser PDF generation.", "Builds PDF report in the browser.", ["line:381 — downloadSingleCvePdf", "line:10 — loadPdfExecutiveSummary"], ["pdf"]),
    ("ui-pdf-ai", "pdfAiSummary.js", "AI summary for PDF", "frontend/src/utils/pdfAiSummary.js:6", "loadPdfExecutiveSummary() → fetchAiSummary POST.", "Fetches optional AI executive summary for PDF.", ["line:6 — loadPdfExecutiveSummary", "line:13 — fetchAiSummary POST"], ["pdf"]),
    ("ui-momentum", "momentumCache.js", "cross-card momentum", "frontend/src/utils/momentumCache.js:12", "setMomentumScore pub/sub for CVECard arrows.", "Shares momentum scores between drawer and cards.", ["line:12 — setMomentumScore", "line:29 — useMomentumScore hook"], ["cve-detail"]),
    ("ui-dead-theme", "light-theme.css", "not imported", "frontend/src/theme/light-theme.css:1", "Light theme CSS exists but is never imported.", "Unused light theme stylesheet (dark-only app).", ["line:1 — zero imports in frontend/src"], ["all"]),
]
for i, row in enumerate(detail_ui):
    nodes.append(
        N(
            row[0],
            "detail-tools",
            row[1],
            row[2],
            col_x("detail-tools"),
            y(i),
            color="service",
            role=row[4],
            plain=row[5],
            path=row[3],
            notes=row[6],
            tag=row[7],
        )
    )

# ── Edges ──────────────────────────────────────────────────
def E(fr, to, kind, label, tags):
    t = tags + (["all"] if "all" not in tags else [])
    return {"from": fr, "to": to, "kind": kind, "label": label, "tag": t}


edges = [
    # Critical spine
    E("ext-nvd", "job-nvd-sync", "critical", "NVD REST delta", ["overview"]),
    E("job-nvd-sync", "svc-nvd-feed", "critical", "fetch_nvd_cve_updates()", ["overview"]),
    E("svc-nvd-feed", "svc-resilient", "normal", "resilient_get", ["overview", "scheduler"]),
    E("job-nvd-sync", "svc-upsert", "critical", "upsert_cves()", ["overview", "scheduler"]),
    E("svc-upsert", "db-cves", "critical", "INSERT cves", ["overview", "scheduler"]),
    E("router-cves", "db-cves", "critical", "GET /api/cves SQL", ["overview"]),
    E("fe-api", "router-cves", "critical", "GET /api/cves", ["overview"]),
    E("ui-cve-feed", "fe-api", "critical", "fetchCVEs()", ["overview"]),
    E("ui-cve-feed", "ui-cve-card", "critical", "render rows", ["overview"]),
    E("ui-cve-card", "fe-drawer-ctrl", "normal", "click → drawer", ["overview", "cve-detail"]),
    E("fe-drawer-ctrl", "fe-api", "normal", "fetchCVE()", ["cve-detail"]),
    E("fe-api", "router-cves", "normal", "GET /api/cves/{id}", ["cve-detail"]),

    # Startup / scheduler → DB
    E("main-py", "router-cves", "mount", "include_router", ["overview"]),
    E("main-py", "router-brief", "mount", "include_router", ["brief"]),
    E("main-py", "router-ioc", "mount", "include_router", ["ioc"]),
    E("main-py", "router-forge", "mount", "include_router", ["forge"]),
    E("main-py", "router-atlas", "mount", "include_router", ["incidents"]),
    E("main-py", "router-config", "mount", "include_router", ["asset-match"]),
    E("main-py", "router-ai", "mount", "include_router", ["pdf"]),
    E("main-py", "svc-backup", "normal", "ensure_db_or_restore", ["backup"]),
    E("job-startup", "job-nvd-sync", "normal", "bootstrap if <10 CVEs", ["overview", "scheduler"]),
    E("ext-kev", "job-kev", "api", "fetch_kev()", ["scheduler"]),
    E("job-kev", "db-cves", "db", "is_kev flags", ["scheduler"]),
    E("job-kev", "db-kev", "db", "kev_deadlines", ["scheduler"]),
    E("ext-epss", "job-epss", "api", "fetch_epss()", ["scheduler"]),
    E("job-epss", "db-cves", "db", "epss_score column", ["scheduler"]),
    E("job-epss", "db-epss-hist", "db", "epss_history rows", ["scheduler"]),
    E("ext-mitre-stix", "job-mitre", "api", "refresh_mitre_data()", ["scheduler"]),
    E("job-mitre", "db-mitre", "db", "mitre_* tables", ["scheduler"]),
    E("ext-atlas-yaml", "job-mitre", "api", "refresh_atlas_data()", ["scheduler"]),
    E("job-mitre", "db-atlas", "db", "atlas_* tables", ["scheduler"]),
    E("ext-otx", "job-otx", "api", "run_otx_nightly_correlation()", ["correlation", "scheduler"]),
    E("job-otx", "db-otx", "db", "otx_* tables", ["correlation"]),
    E("ext-rss", "job-incident", "api", "fetch_all_incident_news_parallel()", ["incidents"]),
    E("job-incident", "svc-case-feed", "normal", "build_incident_feed_snapshot", ["incidents"]),
    E("job-exploit", "db-exploits", "db", "cve_exploits sync", ["scheduler"]),
    E("job-correlation", "svc-correlation", "normal", "run_nightly_correlation()", ["correlation"]),
    E("svc-correlation", "db-corr", "db", "correlation_* write", ["correlation"]),
    E("job-vulnrich", "db-cves", "db", "vulnrichment merge", ["scheduler"]),
    E("ext-github", "job-cvelist", "api", "fetch_cvelistv5_delta()", ["scheduler"]),
    E("job-cvelist", "db-cves", "db", "cvelistV5 merge", ["scheduler"]),
    E("job-backup", "svc-backup", "normal", "run_backup()", ["backup"]),
    E("job-backup", "svc-webhooks", "normal", "dead-man alert", ["backup"]),
    E("job-embeddings", "ml-embeddings", "normal", "embeddings sync", ["scheduler"]),
    E("ml-embeddings", "db-embeddings", "db", "cve_embeddings", ["scheduler"]),

    # Detail enrichment (serial latency path)
    E("router-cves", "ext-sploitus", "api", "load_public_exploits_for_cve", ["cve-detail"]),
    E("router-cves", "ext-greynoise", "api", "greynoise_scans_for_cve", ["cve-detail"]),
    E("router-cves", "ext-otx", "api", "load_otx_pulses_for_cve", ["cve-detail"]),
    E("router-cves", "ext-osv", "api", "fetch_osv_by_cve (serial)", ["cve-detail"]),
    E("router-cves", "ext-circl", "api", "enrich_cve_circl (serial)", ["cve-detail"]),
    E("router-cves", "db-cache", "db", "feed_cache read/write", ["cve-detail"]),
    E("router-cves", "svc-scoring", "normal", "POST /api/cves/{id}/risk", ["cve-detail", "asset-match"]),
    E("router-cves", "svc-scoring", "normal", "GET …/momentum", ["cve-detail"]),
    E("svc-scoring", "svc-asset-match", "normal", "resolve_asset_component()", ["asset-match", "cve-detail"]),
    E("router-cves", "svc-correlation", "normal", "GET …/correlation", ["correlation", "cve-detail"]),
    E("ui-drawer", "fe-api", "normal", "fetchCVERisk()", ["cve-detail", "asset-match"]),
    E("fe-api", "router-cves", "mount", "POST /api/cves/{id}/risk", ["cve-detail", "asset-match"]),
    E("ui-drawer", "fe-api", "normal", "fetchCVESentences/Epss/…", ["cve-detail"]),

    # IOC
    E("ui-ioc", "fe-api", "normal", "lookupIOC()", ["ioc"]),
    E("fe-api", "router-ioc", "mount", "POST /api/ioc/lookup", ["ioc"]),
    E("router-ioc", "svc-enrich-ioc", "normal", "lookup_ioc()", ["ioc"]),
    E("svc-enrich-ioc", "db-cache", "db", "ioc_cache 6h TTL", ["ioc"]),
    E("svc-enrich-ioc", "ext-vt", "api", "VT lookup", ["ioc"]),
    E("svc-enrich-ioc", "ext-abuseipdb", "api", "AbuseIPDB", ["ioc"]),
    E("svc-enrich-ioc", "ext-greynoise", "api", "GreyNoise IP", ["ioc"]),
    E("svc-enrich-ioc", "ext-mb", "api", "MalwareBazaar", ["ioc"]),
    E("svc-enrich-ioc", "ext-urlhaus", "api", "URLhaus", ["ioc"]),
    E("svc-enrich-ioc", "ext-otx", "api", "OTX IOC", ["ioc"]),
    E("router-ioc", "svc-rate-limit", "normal", "rate_limit_ioc", ["ioc"]),
    E("router-ioc", "db-usage", "db", "api_usage increment", ["ioc"]),

    # Brief
    E("ui-brief", "fe-api", "normal", "fetchBrief()", ["brief"]),
    E("fe-api", "router-brief", "mount", "GET /api/brief", ["brief"]),
    E("router-brief", "svc-brief", "normal", "build_morning_brief()", ["brief"]),
    E("svc-brief", "db-cves", "db", "priority SQL", ["brief"]),
    E("ui-stats", "fe-api", "normal", "fetchStats()", ["brief"]),
    E("fe-api", "router-stats", "mount", "GET /api/stats", ["brief"]),
    E("ui-heatmap", "fe-api", "normal", "fetchStatsTimeline()", ["brief"]),
    E("ui-charts", "fe-api", "normal", "stats + brief data", ["brief"]),

    # Incidents
    E("ui-case", "fe-api", "normal", "fetchCaseStudyFeed()", ["incidents"]),
    E("fe-api", "router-atlas", "mount", "GET /api/case-studies/feed", ["incidents"]),
    E("router-atlas", "svc-case-feed", "normal", "get_incident_feed()", ["incidents"]),
    E("svc-case-feed", "db-atlas", "db", "ATLAS cards query", ["incidents"]),
    E("svc-case-feed", "db-cache", "db", "RSS snapshot cache", ["incidents"]),

    # Forge
    E("ui-forge", "fe-api", "normal", "fetchForgeCoverage()", ["forge"]),
    E("fe-api", "router-forge", "mount", "GET /api/forge/coverage", ["forge"]),
    E("ui-forge", "fe-api", "normal", "fetchHuntPack()", ["forge"]),
    E("router-forge", "db-hunt", "db", "hunt_packs CRUD", ["forge"]),
    E("router-forge", "db-mitre", "db", "technique coverage", ["forge"]),

    # PDF / AI
    E("ui-drawer", "ui-pdf", "normal", "downloadSingleCvePdf()", ["pdf"]),
    E("ui-pdf", "ui-pdf-ai", "normal", "loadPdfExecutiveSummary()", ["pdf"]),
    E("ui-pdf-ai", "fe-api", "normal", "fetchAiSummary()", ["pdf"]),
    E("fe-api", "router-ai", "mount", "POST /api/ai/summary", ["pdf"]),
    E("router-ai", "svc-ai", "normal", "generate_executive_summary()", ["pdf"]),
    E("svc-ai", "ext-groq", "api", "_call_groq primary", ["pdf"]),
    E("svc-ai", "ext-anthropic", "api", "_call_anthropic fallback", ["pdf"]),

    # Asset match
    E("fe-asset-ctx", "fe-api", "normal", "fetchCveAssetMatch()", ["asset-match"]),
    E("fe-api", "router-cves", "mount", "POST /api/cves/match", ["asset-match"]),
    E("router-cves", "svc-matching", "normal", "score_cve_for_assets()", ["asset-match"]),
    E("fe-main", "fe-risk", "normal", "fetchAndCacheRiskWeights()", ["asset-match", "overview"]),
    E("fe-risk", "fe-api", "mount", "GET /api/config/risk", ["asset-match"]),
    E("fe-api", "router-config", "mount", "GET /api/config/risk", ["asset-match"]),
    E("router-config", "svc-scoring", "normal", "momentum weights constants", ["asset-match"]),

    # Shell wiring
    E("fe-main", "fe-app", "normal", "render App", ["overview"]),
    E("fe-app", "ui-cve-feed", "normal", "FEED tab panel", ["overview"]),
    E("fe-app", "ui-drawer", "normal", "drawer host", ["cve-detail"]),
    E("fe-app", "ui-watchlist", "normal", "useWatchlist()", ["overview"]),
    E("ui-watchlist", "fe-api", "normal", "fetchWatchlist()", ["overview"]),
    E("fe-api", "router-watchlist", "mount", "GET /api/watchlist", ["overview"]),

    # Resilient client shared
    E("svc-nvd-feed", "ext-nvd", "api", "httpx GET NVD", ["scheduler"]),
    E("router-health", "svc-resilient", "normal", "circuit registry", ["all"]),
    E("job-incident", "svc-resilient", "normal", "RSS httpx", ["incidents"]),
]

KNOWN_BUGS = {
    "db-cves": [
        {
            "sev": "med",
            "ref": "backend/database.py:18",
            "t": "All DB access in one ~2441-line file — single-writer bottleneck under concurrent ingest jobs",
        }
    ],
    "main-py": [
        {
            "sev": "low",
            "ref": "backend/main.py:11",
            "t": "load_dotenv() without override — stale process env silently wins over .env file changes",
        }
    ],
    "router-cves": [
        {
            "sev": "med",
            "ref": "backend/routers/cves.py:854",
            "t": "get_cve runs Sploitus, GreyNoise, OTX, OSV, CIRCL serially — detail drawer latency stacks",
        }
    ],
}

FIXES = {}

# Validate node ids in edges
node_ids = {n["id"] for n in nodes}
for e in edges:
    if e["from"] not in node_ids or e["to"] not in node_ids:
        raise SystemExit(f"Bad edge: {e['from']} -> {e['to']}")

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>BRIEFR Architecture Map</title>
<style>
:root {
  --bg: #0F0F0F; --panel: #161616; --panel-2: #1c1c1c; --border: #2a2a2a;
  --text: #e8e8e8; --muted: #8a8a8a;
  --client: #4ea1ff; --route: #7bd389; --service: #c792ea;
  --db: #ffb86b; --external: #ff6b9d; --critical: #ff3860;
  --accent: #f5b942;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: var(--bg); color: var(--text); font: 13px/1.5 system-ui, sans-serif; height: 100vh; display: flex; flex-direction: column; overflow: hidden; }
header { background: var(--panel); border-bottom: 1px solid var(--border); padding: 10px 16px; flex-shrink: 0; }
header h1 { font-size: 15px; font-weight: 600; margin-bottom: 8px; }
.chips { display: flex; flex-wrap: wrap; gap: 6px; }
.chip { background: var(--panel-2); border: 1px solid var(--border); color: var(--muted); padding: 4px 10px; border-radius: 14px; cursor: pointer; font-size: 11px; transition: all .15s; }
.chip:hover { border-color: var(--accent); color: var(--text); }
.chip.active { background: #2a2200; border-color: var(--accent); color: var(--accent); }
main { display: flex; flex: 1; overflow: hidden; }
#canvas-wrap { flex: 1; position: relative; overflow: hidden; cursor: grab; }
#canvas-wrap.dragging { cursor: grabbing; }
#svg-root { display: block; width: 100%; height: 100%; }
.controls { position: absolute; bottom: 16px; left: 16px; display: flex; gap: 6px; z-index: 5; }
.controls button { background: var(--panel); border: 1px solid var(--border); color: var(--text); padding: 6px 12px; border-radius: 6px; cursor: pointer; font-size: 12px; }
.controls button:hover { border-color: var(--accent); }
#sidebar { width: 360px; background: var(--panel); border-left: 1px solid var(--border); overflow-y: auto; flex-shrink: 0; padding: 16px; }
#sidebar h2 { font-size: 14px; margin-bottom: 8px; }
#sidebar h3 { font-size: 11px; text-transform: uppercase; letter-spacing: .06em; color: var(--muted); margin: 14px 0 6px; }
#sidebar p, #sidebar li { font-size: 12px; color: #ccc; }
#sidebar .plain { color: var(--accent); font-style: italic; margin: 8px 0; }
#sidebar .path { font-family: monospace; font-size: 11px; color: var(--client); word-break: break-all; }
#sidebar ul { padding-left: 16px; }
#sidebar .edge-list { font-size: 11px; font-family: monospace; }
#sidebar .finding { background: var(--panel-2); border-left: 3px solid var(--accent); padding: 8px 10px; margin: 6px 0; font-size: 12px; }
#sidebar .dead { color: var(--critical); font-weight: 600; }
.bug-item.high { border-left: 3px solid var(--critical); }
.bug-item.med { border-left: 3px solid #ff7a45; }
.bug-item.low { border-left: 3px solid var(--muted); }
.bug-item { font-size: 11px; margin: 4px 0; padding: 4px 8px; background: var(--panel-2); border-radius: 4px; }
.cluster-label { fill: var(--muted); font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: .08em; }
.cluster-box { fill-opacity: .06; stroke-width: 1; rx: 8; }
.node { cursor: pointer; transition: opacity .2s; }
.node.dimmed { opacity: .18; }
.node rect { stroke-width: 1.4; rx: 5; }
.node.critical rect { stroke-width: 2.2; filter: drop-shadow(0 0 8px var(--critical)); }
.node text { pointer-events: none; }
.node-label { fill: var(--text); font-size: 10.5px; font-weight: 500; }
.node-sub { fill: var(--muted); font-size: 9px; }
.node-sub.dead { fill: var(--critical); }
.edge { fill: none; stroke-width: 1.3; }
.edge.dimmed { opacity: .08; }
.edge-label { fill: var(--muted); font-size: 8.5px; font-family: monospace; }
.legend { position: absolute; top: 12px; right: 12px; background: var(--panel); border: 1px solid var(--border); border-radius: 8px; padding: 10px 12px; font-size: 10px; z-index: 5; }
.legend-item { display: flex; align-items: center; gap: 6px; margin: 3px 0; color: var(--muted); }
.legend-swatch { width: 20px; height: 3px; border-radius: 2px; }
</style>
</head>
<body>
<header>
  <h1>BRIEFR — Interactive Architecture Map</h1>
  <div class="chips" id="filter-chips"></div>
</header>
<main>
  <div id="canvas-wrap">
    <svg id="svg-root" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <marker id="arrow-critical" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon points="0 0, 8 3, 0 6" fill="#ff3860"/></marker>
        <marker id="arrow-api" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon points="0 0, 8 3, 0 6" fill="#ff7a45"/></marker>
        <marker id="arrow-db" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon points="0 0, 8 3, 0 6" fill="#ffb86b"/></marker>
        <marker id="arrow-mount" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon points="0 0, 8 3, 0 6" fill="#4ea1ff"/></marker>
        <marker id="arrow-normal" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon points="0 0, 8 3, 0 6" fill="#666"/></marker>
      </defs>
      <g id="viewport">
        <g id="clusters-layer"></g>
        <g id="edges-layer"></g>
        <g id="nodes-layer"></g>
      </g>
    </svg>
    <div class="controls">
      <button id="btn-fit">Fit</button>
      <button id="btn-zoom-in">+</button>
      <button id="btn-zoom-out">−</button>
    </div>
    <div class="legend">
      <div class="legend-item"><span class="legend-swatch" style="background:#ff3860"></span> critical path</div>
      <div class="legend-item"><span class="legend-swatch" style="background:#ff7a45"></span> external API</div>
      <div class="legend-item"><span class="legend-swatch" style="background:#ffb86b"></span> database</div>
      <div class="legend-item"><span class="legend-swatch" style="background:#4ea1ff"></span> mount / HTTP</div>
      <div class="legend-item"><span class="legend-swatch" style="background:#666"></span> normal call</div>
    </div>
  </div>
  <aside id="sidebar"></aside>
</main>
<script>
const clusters = __CLUSTERS__;

const N = (id, cluster, label, sub, x, y, w, h, color, opts = {}) =>
  ({ id, cluster, label, sub, x, y, w, h, color, ...opts });

const nodes = __NODES__;

const edges = __EDGES__;

const FIXES = __FIXES__;
const KNOWN_BUGS = __KNOWN_BUGS__;

const COLOR_MAP = { client: '#4ea1ff', route: '#7bd389', service: '#c792ea', db: '#ffb86b', external: '#ff6b9d', accent: '#f5b942' };
const CLUSTER_FILL = { external: '#ff6b9d', scheduler: '#f5b942', sqlite: '#ffb86b', fastapi: '#7bd389', 'react-shell': '#4ea1ff', 'feed-brief': '#c792ea', 'detail-tools': '#c792ea' };
const EDGE_COLOR = { critical: '#ff3860', api: '#ff7a45', db: '#ffb86b', mount: '#4ea1ff', normal: '#666' };
const FILTERS = [
  { id: 'overview', label: 'Overview' },
  { id: 'cve-detail', label: 'CVE Detail' },
  { id: 'ioc', label: 'IOC Lookup' },
  { id: 'brief', label: 'Morning Brief' },
  { id: 'scheduler', label: 'Scheduler' },
  { id: 'incidents', label: 'Incidents' },
  { id: 'forge', label: 'Forge' },
  { id: 'correlation', label: 'Correlation' },
  { id: 'pdf', label: 'PDF / AI' },
  { id: 'asset-match', label: 'Asset Match' },
  { id: 'backup', label: 'Backup' },
  { id: 'all', label: 'Show all' },
];

let activeFilter = 'overview';
let selectedId = null;
let hoveredId = null;
let pan = { x: 20, y: 20 };
let scale = 0.55;
let dragging = false;
let dragStart = null;

const nodeMap = Object.fromEntries(nodes.map(n => [n.id, n]));
const chipsEl = document.getElementById('filter-chips');
const sidebarEl = document.getElementById('sidebar');
const viewport = document.getElementById('viewport');
const wrap = document.getElementById('canvas-wrap');

function bugCount(id) { return (KNOWN_BUGS[id] || []).length; }

function renderChips() {
  chipsEl.innerHTML = FILTERS.map(f =>
    `<button class="chip${activeFilter === f.id ? ' active' : ''}" data-filter="${f.id}">${f.label}</button>`
  ).join('');
  chipsEl.querySelectorAll('.chip').forEach(btn => {
    btn.addEventListener('click', () => { activeFilter = btn.dataset.filter; selectedId = null; render(); });
  });
}

function nodeVisible(n) {
  if (activeFilter === 'all') return true;
  return n.tag.includes(activeFilter);
}

function edgeVisible(e) {
  if (activeFilter === 'all') return true;
  return e.tag.includes(activeFilter);
}

function connectedIds(id) {
  const s = new Set([id]);
  edges.forEach(e => {
    if (e.from === id) s.add(e.to);
    if (e.to === id) s.add(e.from);
  });
  return s;
}

function edgePath(e) {
  const a = nodeMap[e.from], b = nodeMap[e.to];
  if (!a || !b) return '';
  const x1 = a.x + a.w, y1 = a.y + a.h / 2;
  const x2 = b.x, y2 = b.y + b.h / 2;
  const gutter = Math.max(40, (x2 - x1) * 0.42);
  const cx1 = x1 + gutter, cx2 = x2 - gutter;
  return `M ${x1} ${y1} C ${cx1} ${y1}, ${cx2} ${y2}, ${x2} ${y2}`;
}

function edgeLabelPos(e, idx) {
  const a = nodeMap[e.from], b = nodeMap[e.to];
  if (!a || !b) return { x: 0, y: 0 };
  const x1 = a.x + a.w, y1 = a.y + a.h / 2;
  const x2 = b.x, y2 = b.y + b.h / 2;
  const mid = { x: (x1 + x2) / 2, y: (y1 + y2) / 2 - 6 + (idx % 4) * 9 };
  return mid;
}

function renderClusters() {
  const layer = document.getElementById('clusters-layer');
  layer.innerHTML = clusters.map(c => {
    const col = CLUSTER_FILL[c.id] || '#4ea1ff';
    return `<rect class="cluster-box" x="${c.x}" y="${c.y}" width="${c.w}" height="${c.h}" fill="${col}" stroke="${col}"/>
      <text class="cluster-label" x="${c.x + c.w/2}" y="${c.y + 18}" text-anchor="middle">${c.label}</text>`;
  }).join('');
}

function renderGraph() {
  const focusId = hoveredId || selectedId;
  const focusSet = focusId ? connectedIds(focusId) : null;
  let edgeIdx = 0;

  const edgesLayer = document.getElementById('edges-layer');
  edgesLayer.innerHTML = edges.map((e) => {
    const fromNode = nodeMap[e.from];
    const toNode = nodeMap[e.to];
    if (!fromNode || !toNode) return '';
    if (activeFilter !== 'all' && !edgeVisible(e) && !(nodeVisible(fromNode) || nodeVisible(toNode))) return '';
    if (activeFilter !== 'all' && !edgeVisible(e)) return '';
    const dim = focusSet && (!focusSet.has(e.from) || !focusSet.has(e.to));
    const col = EDGE_COLOR[e.kind] || '#666';
    const marker = `url(#arrow-${e.kind in EDGE_COLOR ? e.kind : 'normal'})`;
    const path = edgePath(e);
    const lp = edgeLabelPos(e, edgeIdx++);
    const showLabel = activeFilter === 'all' || e.kind === 'critical' || (focusSet && focusSet.has(e.from) && focusSet.has(e.to));
    return `<path class="edge${dim ? ' dimmed' : ''}" d="${path}" stroke="${col}" marker-end="${marker}"/>
      ${showLabel ? `<text class="edge-label" x="${lp.x}" y="${lp.y}" text-anchor="middle">${e.label}</text>` : ''}`;
  }).join('');

  const nodesLayer = document.getElementById('nodes-layer');
  nodesLayer.innerHTML = nodes.map(n => {
    if (activeFilter !== 'all' && !nodeVisible(n)) return '';
    const dim = focusSet && !focusSet.has(n.id);
    const col = COLOR_MAP[n.color] || '#888';
    const isDead = (n.sub || '').includes('DEAD');
    const bc = bugCount(n.id);
    const badge = bc ? `<circle cx="${n.x+n.w-8}" cy="${n.y+8}" r="7" fill="#a33"/><text x="${n.x+n.w-8}" y="${n.y+11}" text-anchor="middle" fill="#fff" font-size="8">${bc}</text>` : '';
    return `<g class="node${n.critical ? ' critical' : ''}${dim ? ' dimmed' : ''}" data-id="${n.id}">
      <rect x="${n.x}" y="${n.y}" width="${n.w}" height="${n.h}" fill="${col}18" stroke="${col}"/>
      <text class="node-label" x="${n.x+8}" y="${n.y+18}">${n.label}</text>
      <text class="node-sub${isDead ? ' dead' : ''}" x="${n.x+8}" y="${n.y+32}">${n.sub}</text>
      ${badge}
    </g>`;
  }).join('');

  nodesLayer.querySelectorAll('.node').forEach(g => {
    g.addEventListener('mouseenter', () => { hoveredId = g.dataset.id; renderGraph(); renderSidebar(); });
    g.addEventListener('mouseleave', () => { hoveredId = null; renderGraph(); renderSidebar(); });
    g.addEventListener('click', ev => { ev.stopPropagation(); selectedId = g.dataset.id; renderGraph(); renderSidebar(); });
  });
}

function defaultSidebar() {
  const nc = nodes.length, ec = edges.length, cc = nodes.filter(n => n.critical).length;
  return `<h2>Notable findings from this map</h2>
    <div class="finding"><strong>Dead code (zero production callers):</strong>
      <span class="dead">build_plain_summary</span> (enrichment/cve.py:93),
      <span class="dead">fetch_vulnrichment_for_cve</span> + <span class="dead">preview_merge</span> (vulnrichment.py:141/149),
      <span class="dead">lookup_greynoise</span> alias (extended.py:685).
    </div>
    <div class="finding"><strong>Risk score canonical on backend:</strong> <code>POST /api/cves/{id}/risk</code> → <code>scoring/risk.py:calculate_risk_score()</code>; frontend <code>riskScore.js</code> is UI helpers only.</div>
    <div class="finding"><strong>database.py maintenance seam:</strong> ~2441 lines with all 26 tables and inline <code>init_db()</code> migrations — no Alembic; single file is the DB access bottleneck.</div>
    <div class="finding"><strong>Env-var wins over .env:</strong> <code>main.py:11</code> calls <code>load_dotenv()</code> without <code>override=True</code> — process environment (Cursor Secrets) always beats <code>backend/.env</code>; restart required after secret changes.</div>
    <div class="finding"><strong>light-theme.css never imported:</strong> <code>frontend/src/theme/light-theme.css</code> exists but no import in <code>main.jsx</code> — app is dark-mode only.</div>
    <div class="finding"><strong>ML / embeddings gated:</strong> <code>ml/embeddings.py</code>, <code>cve_embeddings</code> table, and <code>embeddings_backfill</code> scheduler job are no-ops unless <code>EMBEDDINGS_ENABLED=1</code> (default off). Same for <code>LLM_PRODUCT_EXTRACTION_ENABLED</code>.</div>
    <div class="finding"><strong>Two cache strategies:</strong> <code>ioc_cache</code> fixed 6 h TTL (<code>database.py:1384</code>) vs <code>feed_cache</code> per-key <code>max_age_hours</code> snapshot pattern (<code>database.py:1407</code>) — different semantics in one DB.</div>
    <div class="finding"><strong>Serial external calls:</strong> <code>get_cve</code> (<code>routers/cves.py:854–911</code>) awaits Sploitus, GreyNoise, OTX, OSV, and CIRCL sequentially — detail drawer latency stacks on every open.</div>
    <h3>Critical path (spine)</h3>
    <p style="font-size:12px;color:#aaa">NVD API → nvd_incremental_sync → fetch_nvd_cve_updates → upsert_cves → cves → list_cves → fetchCVEs → CVEFeed.loadPage → CVECard</p>
    <h3>Stats</h3>
    <p style="font-size:12px;color:#aaa">${nc} nodes · ${ec} edges · ${cc} critical nodes</p>
    <p style="font-size:11px;color:#666;margin-top:12px">Click a node for details. Scroll to zoom. Drag to pan.</p>`;
}

function renderSidebar() {
  const id = hoveredId || selectedId;
  if (!id || !nodeMap[id]) { sidebarEl.innerHTML = defaultSidebar(); return; }
  const n = nodeMap[id];
  const incoming = edges.filter(e => e.to === id).map(e => `${e.from} → ${e.label}`);
  const outgoing = edges.filter(e => e.from === id).map(e => `→ ${e.to}: ${e.label}`);
  const bugs = (KNOWN_BUGS[id] || []).map(b => `<div class="bug-item ${b.sev}">[${b.sev}] ${b.t} <span style="color:#666">(${b.ref})</span></div>`).join('');

  sidebarEl.innerHTML = `
    <h2>${n.label}</h2>
    <p class="path">${n.path}</p>
    <p style="margin-top:8px">${n.role}</p>
    <p class="plain">${n.plain}</p>
    <h3>Notes</h3><ul>${n.notes.map(x => `<li>${x}</li>`).join('')}</ul>
    <h3>Tags</h3><p style="font-size:11px;color:#888">${n.tag.filter(t => t !== 'all').join(', ')}</p>
    <h3>Incoming (${incoming.length})</h3><div class="edge-list">${incoming.map(x=>`<div>${x}</div>`).join('') || '<span style="color:#666">none</span>'}</div>
    <h3>Outgoing (${outgoing.length})</h3><div class="edge-list">${outgoing.map(x=>`<div>${x}</div>`).join('') || '<span style="color:#666">none</span>'}</div>
    ${bugs ? `<h3>Known issues</h3>${bugs}` : ''}
  `;
}

function applyTransform() {
  viewport.setAttribute('transform', `translate(${pan.x},${pan.y}) scale(${scale})`);
}

function fitView() {
  const bbox = { x: 0, y: 0, w: 1680, h: 1220 };
  const rect = wrap.getBoundingClientRect();
  const s = Math.min(rect.width / bbox.w, rect.height / bbox.h) * 0.94;
  scale = Math.max(0.3, Math.min(1.4, s));
  pan.x = (rect.width - bbox.w * scale) / 2;
  pan.y = (rect.height - bbox.h * scale) / 2;
  applyTransform();
}

function render() { renderGraph(); renderSidebar(); }

wrap.addEventListener('mousedown', e => {
  if (e.button !== 0) return;
  if (e.target.closest('.node') || e.target.closest('button')) return;
  dragging = true; dragStart = { x: e.clientX - pan.x, y: e.clientY - pan.y };
  wrap.classList.add('dragging');
});
window.addEventListener('mousemove', e => {
  if (!dragging) return;
  pan.x = e.clientX - dragStart.x;
  pan.y = e.clientY - dragStart.y;
  applyTransform();
});
window.addEventListener('mouseup', () => { dragging = false; wrap.classList.remove('dragging'); });
wrap.addEventListener('click', e => {
  if (e.target.closest('.node')) return;
  selectedId = null; render();
});
wrap.addEventListener('wheel', e => {
  e.preventDefault();
  const rect = wrap.getBoundingClientRect();
  const mx = e.clientX - rect.left;
  const my = e.clientY - rect.top;
  const delta = e.deltaY > 0 ? 0.92 : 1.08;
  const newScale = Math.max(0.22, Math.min(2.8, scale * delta));
  pan.x = mx - (mx - pan.x) * (newScale / scale);
  pan.y = my - (my - pan.y) * (newScale / scale);
  scale = newScale;
  applyTransform();
}, { passive: false });

document.getElementById('btn-fit').addEventListener('click', fitView);
document.getElementById('btn-zoom-in').addEventListener('click', () => { scale = Math.min(2.8, scale * 1.15); applyTransform(); });
document.getElementById('btn-zoom-out').addEventListener('click', () => { scale = Math.max(0.22, scale / 1.15); applyTransform(); });
window.addEventListener('resize', fitView);

renderChips();
renderClusters();
render();
fitView();
</script>
</body>
</html>
"""

html = (
    HTML_TEMPLATE.replace("__CLUSTERS__", json.dumps(clusters, indent=2))
    .replace("__NODES__", json.dumps(nodes, indent=2))
    .replace("__EDGES__", json.dumps(edges, indent=2))
    .replace("__FIXES__", json.dumps(FIXES, indent=2))
    .replace("__KNOWN_BUGS__", json.dumps(KNOWN_BUGS, indent=2))
)

OUT.write_text(html, encoding="utf-8")
print(f"Wrote {OUT}")
print(f"Nodes: {len(nodes)}, Edges: {len(edges)}, Critical nodes: {sum(1 for n in nodes if n.get('critical'))}")
