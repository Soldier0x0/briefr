#!/usr/bin/env python3
"""Generate TECHNICAL_INVENTORY.xlsx from structured data."""

from pathlib import Path

try:
    from openpyxl import Workbook
    from openpyxl.utils import get_column_letter
except ImportError:
    raise SystemExit("Install openpyxl: pip install openpyxl")

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "TECHNICAL_INVENTORY.xlsx"


def autosize(ws):
    for col in ws.columns:
        max_len = 0
        letter = get_column_letter(col[0].column)
        for cell in col:
            if cell.value is not None:
                max_len = max(max_len, len(str(cell.value)))
        ws.column_dimensions[letter].width = min(max(max_len + 2, 10), 60)


def main():
    wb = Workbook()

    # Sheet 1: Tech Stack
    ws = wb.active
    ws.title = "Tech Stack"
    ws.append(["Component", "Technology", "Version", "Purpose"])
    for row in [
        ("API framework", "FastAPI", "0.136.3", "REST API, OpenAPI, validation"),
        ("ASGI server", "uvicorn", "0.48.0", "Production HTTP server"),
        ("HTTP client", "httpx", "0.28.1", "Async external API calls"),
        ("Scheduler", "APScheduler", "3.11.2", "7 background jobs"),
        ("Database", "SQLite + aiosqlite", "0.22.1", "Local persistence"),
        ("Validation", "Pydantic", "2.13.4", "Request models"),
        ("UI", "React", "18.3.1", "Analyst SPA"),
        ("Build", "Vite", "5.4.1", "Dev and production bundle"),
        ("PDF", "jsPDF + html2canvas", "4.2.1 / 1.4.1", "Client PDF reports"),
    ]:
        ws.append(row)
    autosize(ws)

    # Sheet 2: Database Schema
    ws2 = wb.create_sheet("Database Schema")
    ws2.append(["Table", "Column", "Type", "Constraints", "Description"])
    schema = [
        ("cves", "cve_id", "TEXT", "PRIMARY KEY", "CVE identifier"),
        ("cves", "description", "TEXT", "", "NVD description"),
        ("cves", "cvss_score", "REAL", "", "CVSS v3 base"),
        ("cves", "severity", "TEXT", "", "CRITICAL/HIGH/MEDIUM/LOW"),
        ("cves", "published", "TEXT", "", "Publish timestamp"),
        ("cves", "modified", "TEXT", "", "Last modified"),
        ("cves", "affected_products", "TEXT", "DEFAULT '[]'", "JSON vendor:product"),
        ("cves", "mitre_technique", "TEXT", "", "Primary ATT&CK ID"),
        ("cves", "summary", "TEXT", "", "Plain-English summary"),
        ("cves", "is_kev", "INTEGER", "DEFAULT 0", "CISA KEV flag"),
        ("cves", "epss_score", "REAL", "", "EPSS probability"),
        ("cves", "has_poc", "INTEGER", "DEFAULT 0", "Public PoC flag"),
        ("cves", "patch_available", "INTEGER", "DEFAULT 0", "Patch ref flag"),
        ("cves", "has_ai_context", "INTEGER", "DEFAULT 0", "AI/ML relevance"),
        ("cves", "source_urls", "TEXT", "DEFAULT '[]'", "JSON URLs"),
        ("cves", "cwe_ids", "TEXT", "DEFAULT '[]'", "JSON CWEs"),
        ("cves", "updated_at", "TEXT", "DEFAULT datetime('now')", "Row update"),
        ("cves", "cpe_matches", "TEXT", "DEFAULT '[]'", "JSON CPE matches (migration)"),
        ("ioc_cache", "value", "TEXT", "PRIMARY KEY", "IOC value"),
        ("ioc_cache", "ioc_type", "TEXT", "NOT NULL", "ip/hash/domain"),
        ("ioc_cache", "result", "TEXT", "NOT NULL", "JSON result"),
        ("ioc_cache", "cached_at", "TEXT", "", "6h TTL anchor"),
        ("kev_deadlines", "cve_id", "TEXT", "PRIMARY KEY", "CVE ID"),
        ("feed_cache", "cache_key", "TEXT", "PRIMARY KEY", "Cache key"),
        ("sync_state", "key", "TEXT", "PRIMARY KEY", "e.g. nvd_last_mod_end"),
        ("epss_history", "cve_id", "TEXT", "PK part", "CVE ID"),
        ("epss_history", "score", "REAL", "NOT NULL", "EPSS snapshot"),
        ("epss_history", "recorded_date", "TEXT", "PK part", "Date"),
        ("otx_cve_pulses", "cve_id", "TEXT", "PK part", "CVE ID"),
        ("otx_cve_pulses", "pulse_id", "TEXT", "PK part", "OTX pulse"),
        ("correlation_infrastructure", "cve_id_a", "TEXT", "PK part", "CVE A"),
        ("correlation_infrastructure", "cve_id_b", "TEXT", "PK part", "CVE B"),
        ("correlation_actor", "cve_id", "TEXT", "PK part", "CVE ID"),
        ("correlation_actor", "actor_name", "TEXT", "PK part", "Actor name"),
        ("correlation_temporal", "vendor", "TEXT", "PRIMARY KEY", "Vendor slug"),
        ("mitre_techniques", "technique_id", "TEXT", "PRIMARY KEY", "Txxxx"),
        ("atlas_techniques", "technique_id", "TEXT", "PRIMARY KEY", "AML.Txxxx"),
        ("mitre_groups", "group_id", "TEXT", "PRIMARY KEY", "Gxxxx"),
    ]
    for row in schema:
        ws2.append(row)
    autosize(ws2)

    # Sheet 3: Scheduler Jobs
    ws3 = wb.create_sheet("Scheduler Jobs")
    ws3.append(["Job ID", "Schedule", "Fetches from", "Writes to", "Failure behaviour", "Idempotent"])
    jobs = [
        ("nvd_incremental_sync", "Every NVD_SYNC_INTERVAL_HOURS (default 1h)", "NVD API", "cves, sync_state, feed_cache", "Log; watermark not advanced on fail", "Yes"),
        ("kev_metadata_sync", "Every KEV_SYNC_INTERVAL_MINUTES (default 15m)", "CISA KEV", "kev_deadlines, cves.is_kev", "Log error", "Yes"),
        ("epss_score_sync", "Every EPSS_SYNC_INTERVAL_HOURS (default 6h)", "EPSS CSV/API", "cves, epss_history", "Log error", "Yes"),
        ("weekly_mitre_refresh", "Cron Sun MITRE_REFRESH_HOUR (default 02:00)", "MITRE STIX, ATLAS", "mitre_*, atlas_*, maps", "Log error", "Mostly"),
        ("otx_nightly_correlation", "Cron OTX_CORRELATION (default 02:00 IST)", "OTX API", "otx_*, feed_cache", "Skip if no key", "Yes"),
        ("incident_news_refresh", "Every 4 hours", "6 RSS feeds", "feed_cache", "Per-source errors", "Yes"),
        ("nightly_correlation", "Cron CORRELATION (default 01:00 IST)", "OTX + DB", "correlation_*", "Log; lock skip", "Yes"),
    ]
    for row in jobs:
        ws3.append(row)
    autosize(ws3)

    # Sheet 4: External APIs
    ws4 = wb.create_sheet("External APIs")
    ws4.append(["Service", "Endpoint", "Key env var", "Free tier limit", "Fallback"])
    apis = [
        ("NVD", "services.nvd.nist.gov/rest/json/cves/2.0", "NVD_API_KEY", "50 req/30s with key", "Retry/backoff"),
        ("CISA KEV", "cisa.gov/.../known_exploited_vulnerabilities.json", "", "Unlimited", "[]"),
        ("EPSS", "epss.empiricalsecurity.com CSV", "", "Unlimited", "{}"),
        ("VirusTotal", "virustotal.com/api/v3", "VIRUSTOTAL_API_KEY", "500/day", "Empty fields"),
        ("AbuseIPDB", "api.abuseipdb.com", "ABUSEIPDB_API_KEY", "1000/day", "Skipped"),
        ("GreyNoise", "api.greynoise.io", "GREYNOISE_API_KEY", "50/week", "Unknown"),
        ("OTX", "otx.alienvault.com/api/v1", "OTX_API_KEY", "10k/month", "[]"),
        ("Groq", "api.groq.com", "GROQ_API_KEY", "Console quota", "Anthropic/template"),
        ("Anthropic", "api.anthropic.com", "ANTHROPIC_API_KEY", "Console quota", "Template"),
        ("GitHub", "api.github.com/search/code", "GITHUB_TOKEN", "60/hr anon", "[]"),
    ]
    for row in apis:
        ws4.append(row)
    autosize(ws4)

    # Sheet 5: Risk Scoring
    ws5 = wb.create_sheet("Risk Scoring")
    ws5.append(["Component", "Weight", "Source file"])
    for row in [
        ("Asset profile", 0.35, "frontend/src/scoring/riskScore.js"),
        ("KEV status", 0.25, "frontend/src/scoring/riskScore.js"),
        ("EPSS", 0.15, "frontend/src/scoring/riskScore.js"),
        ("Exploit availability", 0.10, "frontend/src/scoring/riskScore.js"),
        ("CVSS", 0.10, "frontend/src/scoring/riskScore.js"),
        ("Momentum", 0.05, "backend/scoring/risk.py calculate_momentum"),
    ]:
        ws5.append(row)
    ws5.append([])
    ws5.append(["Momentum signal", "Description", "Max contribution"])
    signals = [
        ("epss_rising", "EPSS delta over 14 snapshots", "0.50"),
        ("otx_pulse", "OTX pulse fetched_at recency", "0.50"),
        ("kev_recent", "KEV added within 7 days", "0.40"),
        ("rapid_exploitation", "KEV within 30d of publish", "0.30"),
    ]
    for row in signals:
        ws5.append(row)
    autosize(ws5)

    # Sheet 6: Feature Completion
    ws6 = wb.create_sheet("Feature Completion")
    ws6.append(["Feature", "Status", "Notes"])
    features = [
        ("NVD incremental ingest", "Complete", "Watermark + upsert"),
        ("KEV sync", "Complete", "15m default"),
        ("EPSS sync", "Complete", "History snapshots"),
        ("CVE feed", "Complete", "Max 50/page"),
        ("CVE detail ATLAS", "Partial", "API does not return atlas_techniques"),
        ("IOC lookup", "Complete", "6h cache"),
        ("Risk score v1.1b", "Complete", "Client-side"),
        ("Correlation", "Complete", "6h cache"),
        ("Detection tab", "Complete", "Sigma/Elastic"),
        ("PDF + AI summary", "Complete", "Groq/Anthropic/template"),
        ("POST /api/investigation/summary", "Broken", "Undefined import main.py:1331"),
        ("Authentication", "Not implemented", "v1.1 by design"),
        ("Repository pattern", "Not implemented", "v1.2"),
    ]
    for row in features:
        ws6.append(row)
    autosize(ws6)

    wb.save(OUT)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
