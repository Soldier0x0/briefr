"""Gap-fill Q&A for work merged after issue #498 (2026-07-13).

Merged into existing interview chapters by slug; adds one new chapter for
Security Architecture / threat modeling (PM-3, PM-4, TM-6).
"""

from __future__ import annotations

GAP_BY_SLUG: dict[str, list[dict]] = {
    "iv-correlation-scoring": [
        {
            "category": "implementation",
            "q": "What is correlation v3 Phase 4 and when did it ship?",
            "a": "CORR-PR-6…13 (#501–#513) added observation-time semantics, read-time freshness decay, pulse families, ThreatFox corroboration, alias-aware attribution conflicts, analyst confirm feedback, <code>correlation_metrics</code> snapshots, and feed-boost gating for watchlist campaign peers. Nightly engine still reads Postgres only—no live OTX in the correlation run.",
        },
        {
            "category": "implementation",
            "q": "Why capture observed_at on OTX pulse IOCs?",
            "a": "CORR-PR-6 stores when an IOC was observed on a pulse so lifecycle, momentum, and freshness decay use observation time—not just ingest time. Prevents stale intel from looking newly active after a re-sync.",
        },
        {
            "category": "failure",
            "q": "How does read-time freshness decay work?",
            "a": "CORR-PR-8 computes decay at read time so drawer staleness badges reflect age of observations. Postgres GROUP BY for freshness columns is tested—bad SQL here broke production reads before the str() guard fix.",
        },
        {
            "category": "implementation",
            "q": "What are pulse families?",
            "a": "<code>pulse_families</code> table + <code>rebuild_pulse_families</code> clusters pulses by Jaccard similarity on IOC sets (CORR-PR-9). Reduces duplicate campaign cards and powers dedup in Active Campaigns UI.",
        },
        {
            "category": "integration",
            "q": "How does ThreatFox corroboration strengthen IOC edges?",
            "a": "CORR-PR-10: when ThreatFox and OTX agree on infrastructure IOCs, shared-infrastructure lanes get stronger evidence in <code>find_shared_infrastructure_v2</code>. Tests in <code>test_threatfox_corroboration.py</code> lock the behavior.",
        },
        {
            "category": "failure",
            "q": "What is alias-aware attribution conflict?",
            "a": "CORR-PR-11 resolves conflicting actor/alias labels on merged campaigns so analysts do not see contradictory attribution strings on related pulses. Explainable merge—not silent overwrite.",
        },
        {
            "category": "integration",
            "q": "What is the analyst confirm feedback API?",
            "a": "CORR-PR-12 exposes authenticated endpoints for analysts to confirm or reject correlation suggestions—feedback persisted for tuning and UI honesty (Confirm controls in drawer/Intel).",
        },
        {
            "category": "implementation",
            "q": "What does correlation_metrics store?",
            "a": "Daily snapshot rows via <code>snapshot_correlation_metrics</code>—counts of campaigns, lanes, stale factors—used for admin/ops visibility and CORR-PR-13 feed-boost gating decisions.",
        },
        {
            "category": "integration",
            "q": "How does feed-boost gating interact with watchlist?",
            "a": "CORR-PR-13 boosts CVEs linked to pinned campaign peers in feed sort when metrics + confirm state allow—tested in <code>test_feed_watchlist_campaign_sort.py</code>. Does not invent relevance without stack/pin context.",
        },
        {
            "category": "tradeoff",
            "q": "Why client-side OP escalation if correlation is server-side?",
            "a": "Historical latency compromise: OP hero uses cheap signals immediately; campaign escalation merges when correlation loads (<code>CORRELATION_PRECOMPUTE_ENABLED</code> default off). Server-side merge in <code>/risk</code> is the documented future hardening.",
        },
        {
            "category": "performance",
            "q": "Does correlation block drawer open?",
            "a": "Not when precompute is off—<code>POST /api/cves/{id}/risk</code> avoids blocking on correlation snapshot. Intel/campaign sections load asynchronously with staleness callouts.",
        },
        {
            "category": "overview",
            "q": "What lanes does correlation v3 expose?",
            "a": "Campaign clusters, infrastructure/shared IOC, actor/sector signals, temporal patterns—each with structured factors in Postgres, served over REST to Intel tab and semantic search (campaign embeddings E8).",
        },
    ],
    "iv-campaign-ioc": [
        {
            "category": "implementation",
            "q": "How does formatIntelLabel differ from normalize_pulse_name?",
            "a": "Display uses <code>formatIntelLabel</code> (humanized titles, author Part N/M badge). Clustering/matching uses stronger <code>normalize_pulse_name</code>—underscores, Part tokens, punctuation identity only.",
        },
        {
            "category": "integration",
            "q": "How do IOC watchlist hits become webhooks?",
            "a": "<code>ioc_watchlist_hit</code> event type on database-backed destinations; dedupe per <code>(destination_id, event_type, dedupe_key)</code>. Distinct from watchlist KEV/EPSS monitor alerts.",
        },
    ],
    "iv-architecture": [
        {
            "category": "overview",
            "q": "What analyst tabs exist in the main shell?",
            "a": "BRIEF (summary), FEED (CVE list), IOC (live lookup), Incidents/News (RSS + case studies), Forge (ATT&amp;CK/hunt). Tabs use <code>hidden</code> panels—not unmount—to preserve scroll/filters. URL syncs <code>?tab=</code>.",
        },
        {
            "category": "integration",
            "q": "How does RSS link to CVEs?",
            "a": "Incidents ingest parses <code>cve_ids</code> from title/body; cards chip to open drawer; drawer RELATED tab includes <code>related_news</code> on bundle endpoint—bidirectional news↔CVE navigation.",
        },
        {
            "category": "implementation",
            "q": "What is the BRIEF tab?",
            "a": "Executive summary surface for prioritized intel—uses same session auth and scoring API as FEED; auth refresh race (#731) specifically broke BRIEF with concurrent 401s before shared <code>refreshAccessToken()</code> dedupe.",
        },
        {
            "category": "integration",
            "q": "How does MITRE ATLAS appear?",
            "a": "<code>GET /api/case-studies/feed</code> alongside RSS sources in Incidents—separate from ATT&amp;CK Forge navigator corpora refreshed by <code>weekly_mitre_refresh</code>.",
        },
    ],
    "iv-security": [
        {
            "category": "failure",
            "q": "What was the BRIEF refresh race (#731)?",
            "a": "Concurrent 401s each called <code>/api/auth/refresh</code> independently; refresh rotation reuse detection revoked all sessions. Fix: single in-flight <code>refreshAccessToken()</code> in <code>api.js</code>; bootstrap uses <code>fetchMe()</code> only.",
        },
        {
            "category": "security",
            "q": "What is JWT role revalidation (#392)?",
            "a": "Handlers re-check <code>users.is_active</code> and role on sensitive routes—JWT claims alone are not trusted. Deactivated admins lose access immediately.",
        },
        {
            "category": "security",
            "q": "Are LLM summary routes public?",
            "a": "No—<code>GET/POST /api/ai/summary</code> and investigation summary require logged-in session (<code>require_user</code>). Prevents unauthenticated URL proxying to LLM providers.",
        },
        {
            "category": "implementation",
            "q": "What does ADR-006 encrypt?",
            "a": "Secret-typed <code>app_settings</code> keys at rest when <code>BRIEFR_SETTINGS_KEY</code> is set. Without it, secrets remain env/<code>.env</code> only—never written to DB plaintext.",
        },
    ],
    "iv-backend-db": [
        {
            "category": "integration",
            "q": "How do intel snapshots support migration?",
            "a": "<code>scripts/export_intel_snapshot.py</code> exports allowlisted tables per DATA_SNAPSHOT.md (manifest v1); <code>verify_intel_snapshot.py</code> and <code>import_intel_snapshot.py</code> for DR/migration between instances—complements pg_dump, not replacement.",
        },
        {
            "category": "implementation",
            "q": "What is DATABASE_POOL_COMMAND_TIMEOUT_SECONDS?",
            "a": "SQL-only pool command timeout (default 60s)—separate from per-feed HTTP timeouts. Paired with NVD commit-before-enrich so slow HTTP enrich cannot exhaust writers' SQL budget.",
        },
        {
            "category": "failure",
            "q": "What broke on SigmaHQ migration 035?",
            "a": "Unquoted Postgres reserved word <code>references</code> in DDL—fixed with quoting/rename. <code>test_alembic_revisions.py</code> scans for this class of bug; forward-only migrations only.",
        },
    ],
    "iv-ingest-scheduler": [
        {
            "category": "implementation",
            "q": "What is CPE catalog sync (Q3)?",
            "a": "<code>cpe_catalog_sync</code> job (<code>CPE_CATALOG_SYNC_ENABLED=0</code> default) populates <code>software_catalog</code> from NVD CPE 2.3 API with checkpointed full then incremental sync. Powers <code>/api/stack/catalog/suggest</code> typeahead.",
        },
        {
            "category": "performance",
            "q": "How does EPSS identity skip save CPU?",
            "a": "Q5: compare downloaded CSV SHA256 + <code>score_date</code> to <code>sync_state</code>; unchanged file skips gunzip/parse/upsert. Force via admin EPSS force-resync.",
        },
        {
            "category": "implementation",
            "q": "What is stack backfill idempotency (IDEM-A/B)?",
            "a": "<code>claim_run_running</code> atomic gate admits one worker; stale <code>running</code> reclaimed after <code>STACK_BACKFILL_STALE_SECONDS</code>. Procrastinate defer uses per-run <code>queueing_lock</code>; NVD 429 schedules durable resume after 180s when enabled.",
        },
        {
            "category": "integration",
            "q": "What is catch-up mode v1?",
            "a": "Admin time-boxed backlog drain: raises embeddings/correlation caps + LLM pacing headroom; <code>catchup_tick</code> every 5 min nudges eligible work. Still respects <code>api_queue</code> and rate-limit floors.",
        },
    ],
    "iv-ml-embeddings": [
        {
            "category": "integration",
            "q": "How does Program E manual LLM retry work?",
            "a": "<code>GET .../operations/{id}/payload</code> + <code>POST .../retry</code> with replay provenance, circuit-open guard (409 unless <code>force=true</code>), and <code>ai.operations.retry</code> audit. Activity rows show <code>has_payload</code>.",
        },
        {
            "category": "failure",
            "q": "Why skip LLM HTTP on empty CVE text?",
            "a": "<code>llm_payload.py</code> guard at router + clients—prevents quota burn on blank descriptions. Feed Health degraded cards with 'empty LLM response' point operators to AI Operations.",
        },
        {
            "category": "implementation",
            "q": "What is AI-3 quota advisory?",
            "a": "<code>ai/quota.py</code> snapshots provider rate-limit headers into AI Operations provider rows—informational warnings, not hard enforcement (K5 pacing handles batch headroom).",
        },
    ],
    "iv-detection-forge": [
        {
            "category": "implementation",
            "q": "What did detection composer DC-1…DC-4 ship?",
            "a": "Evidence pack + emit Sigma/SIEM/YARA via shared detection engine—no LLM required. Detect tab and Forge hunt-pack generate share the same class router and SigmaHQ index path.",
        },
        {
            "category": "implementation",
            "q": "How does YARA generation use IOC structs?",
            "a": "Deterministic from structured IOC type/value in detection context—<code>test_yara_generator.py</code> guards shapes. Not LLM-invented strings.",
        },
        {
            "category": "overview",
            "q": "What Forge views exist beyond the matrix?",
            "a": "Threat scenarios, proof bench, KEV backlog (<code>?view=backlog</code>), hunt packs, coverage—top tabs switch views; matrix click toggles technique selection (PM-4d).",
        },
        {
            "category": "integration",
            "q": "How does kev_backlog notification deep-link?",
            "a": "Scheduler <code>detection/backlog.py</code> emits <code>kev_backlog</code> to <code>user_notifications</code>; analyst bell opens Forge backlog view for stack coverage gaps.",
        },
    ],
    "iv-frontend-ux": [
        {
            "category": "integration",
            "q": "How does shell URL history interact with Back button?",
            "a": "Intentional tab/Forge/admin page/CVE drawer changes <strong>push</strong> history; cosmetic param hygiene <strong>replaces</strong>. Back closes drawer before leaving tab; Forge→CVE uses router navigate not <code>location.assign</code>.",
        },
        {
            "category": "implementation",
            "q": "What is the Background sync portal UI?",
            "a": "Portaled Radix dropdown on header—groups api_queue tasks by provider, distinguishes waiting vs queued, collision-aware (Program A UX RCA). Distinct from Admin durable outbound jobs panel.",
        },
        {
            "category": "implementation",
            "q": "What UX RCA changed in the drawer?",
            "a": "PR-A: Overview IA, L-edge panels, accent-ghost actions, Active Campaigns default closed, MITRE hint only when techniques exist, tabs stay mounted after first visit. PR-D: Forge matrix EmptyState, honest campaign copy.",
        },
        {
            "category": "implementation",
            "q": "What is Track E command palette?",
            "a": "⌘K wayfinding—keyboard accessible, portaled. Part of UI-M design system completion alongside Radix primitives and token lint gates.",
        },
    ],
    "iv-api-ops": [
        {
            "category": "implementation",
            "q": "How do multi-destination webhooks work (PR12b/c)?",
            "a": "CRUD on <code>webhook_destinations</code> (20/kind cap), per-destination event subscriptions, masked config on GET, health cards with 24h ok/fail, test POST even when disabled. Env vs DB source badges in admin UI.",
        },
        {
            "category": "failure",
            "q": "What are crash-stranded webhook dedupe claims?",
            "a": "IDEM-D: dedupe row without delivery log after worker crash—<code>cache_retention_cleanup</code> sweeps claims older than 1h grace so alerts are not silently suppressed forever.",
        },
        {
            "category": "integration",
            "q": "How does the notification center split analyst vs admin?",
            "a": "Analyst header bell: watchlist, IOC, <code>kev_backlog</code>. Admin StatusBar bell: job errors, unhealthy API keys, webhook delivery failures—deep-links to Scheduler/Webhooks/API keys.",
        },
        {
            "category": "implementation",
            "q": "What is API key health vs feed circuit?",
            "a": "Probes persist to <code>api_key_health:{provider}</code> with <code>record_circuit=False</code>—a bad probe does not open the shared circuit used by real LLM/ingest traffic.",
        },
        {
            "category": "integration",
            "q": "What is first-hour onboarding checklist?",
            "a": "Admin System health live checklist (CVE ingest, stack, backups, feeds, posture) until dismissed or complete—reduces time-to-first-value for new operators.",
        },
    ],
    "iv-devops-deploy": [
        {
            "category": "implementation",
            "q": "What did deploy #745 add?",
            "a": "Production-zone install/deploy/service scripts under <code>deploy/</code>—additive compatibility promise for live boxes documented in OPERATIONS.md. Not a full platform docker-compose.",
        },
        {
            "category": "integration",
            "q": "What is support pack export?",
            "a": "<code>GET /api/admin/diagnostics/support-pack</code> redacted health + ring-buffer logs; <code>briefr-doctor.sh</code> can download on live host—no secrets in bundle.",
        },
        {
            "category": "implementation",
            "q": "What is corpus drift check?",
            "a": "<code>POST /api/admin/diagnostics/corpus-drift</code> regenerates security architecture generated layer to temp dir and diffs vs committed corpus—CI also runs <code>test_security_architecture_corpus.py</code>.",
        },
    ],
    "iv-product-behavioral": [
        {
            "category": "tradeoff",
            "q": "Why relicense to Apache 2.0 (#748)?",
            "a": "OSI-approved, commercial-friendly, aligns with SigmaHQ/ecosystem expectations—removed BSL/BUSL confusion for self-hosters and contributors.",
        },
        {
            "category": "tradeoff",
            "q": "Why migrate study guide to briefr-maintainer (#751)?",
            "a": "Public repo stays product-focused; deep maintainer/onboarding docs live private. Interview pack ships as <code>maintainer-export/</code> portable drop-in.",
        },
    ],
    "iv-tests-docs": [
        {
            "category": "overview",
            "q": "What ADRs should interviewees know?",
            "a": "ADR-001 intel schema split; ADR-002 OP/scoring; ADR-003 UI tokens/Radix; ADR-004 correlation precompute; ADR-005 component libraries; ADR-006 encrypted settings. PRODUCT_STATUS wins when ADRs lag.",
        },
        {
            "category": "implementation",
            "q": "What does verify-local grep-gate on native controls?",
            "a": "Fails build on native <code>&lt;select&gt;</code> / checkbox in new code—design system §23 amateur defect prevention alongside token lint.",
        },
    ],
}

SECARCH_SEGMENT: dict = {
    "slug": "iv-secarch-threatmodel",
    "page_id": "iv-secarch-threatmodel",
    "chapter_num": "Interview · TBD",
    "title": "Security architecture & threat modeling",
    "dek": "PM-3 ARCH graph, Security posture, TM-6 framework workspaces, and live risk register.",
    "questions": [
        {
            "category": "overview",
            "q": "What is the PM-3 security architecture graph?",
            "a": "Self-documenting corpus: routers, jobs, tables, external sources as nodes; SQL and job edges generated into <code>security_architecture/corpus/</code>. Admin Security posture and ARCH views render the graph with zoom, focus-dim, one-hop SQL edges via <code>database</code> shim.",
        },
        {
            "category": "overview",
            "q": "Where do analysts vs admins see ARCH?",
            "a": "PM-4b/c: analysts no longer edit corpus; <code>/security-architecture</code> redirects to Admin → Security posture. Analyst read-only posture pages (PM-4a): Overview, System Architecture, Trust Boundaries, Attack Surface, Risks.",
        },
        {
            "category": "implementation",
            "q": "How are one-hop SQL edges produced?",
            "a": "PM-3 uses <code>database</code> shim helpers to trace single SQL statements from routers/jobs to tables—focus-only edge draw in UI; external nodes for NVD/OTX/etc. Not runtime dependency for CVE ops.",
        },
        {
            "category": "implementation",
            "q": "What is TM-6 framework workspaces?",
            "a": "Admin Security posture FRAMEWORKS: CWE, OWASP Top 10 2021, CAPEC, STRIDE over live <code>cves.cwe_ids</code> with Scope filters (All / My Stack / Watchlist / KEV + severity). Counts drill to <code>example_cves</code>; unmapped bucket keeps totals honest.",
        },
        {
            "category": "integration",
            "q": "How does live self-stack risk scoring work?",
            "a": "Risk Register rows score structured CPE/affected_products against generated self-stack—product+version = 100, product-only fallback = 55 (version unverified). No description LIKE admission.",
        },
        {
            "category": "failure",
            "q": "What is cap honesty on live self-stack?",
            "a": "API returns <code>live_self_stack</code> stats: <code>candidate_rows</code>, <code>scored_matches</code>, <code>admitted</code>, <code>cap=50</code>. UI shows 'showing X of Y (cap 50)' when matches exceed cap—no silent truncation.",
        },
        {
            "category": "integration",
            "q": "How does corpus drift detection work?",
            "a": "Admin button + CI: regenerate generated layer, diff vs committed YAML/JSON. Catches stale job→table edges when routers change without corpus refresh.",
        },
        {
            "category": "security",
            "q": "Is the security corpus editable by analysts?",
            "a": "No—operator/admin corpus editing removed from analyst ARCH (PM-4b). Reduces risk of unreviewed graph edits on production intel paths.",
        },
        {
            "category": "tradeoff",
            "q": "Why self-documenting architecture vs external CMDB?",
            "a": "Solo/small-team ops: graph stays in-repo, regenerates from code+SQL, powers posture page without third-party sync. Tradeoff: corpus can drift until drift check runs.",
        },
        {
            "category": "implementation",
            "q": "What threat modeling tracks shipped (TM-0…TM-5)?",
            "a": "Foundation for posture views, trust boundaries, attack surface enumeration—feeds Security admin and reader docs. TM-6 extends with framework workspaces over live CVE data.",
        },
        {
            "category": "integration",
            "q": "How does drawer CAPEC/SSVC relate to TM-6?",
            "a": "Drawer shows per-CVE CAPEC chips (CIRCL) and CISA SSVC (Vulnrichment). TM-6 aggregates CWE/OWASP/CAPEC/STRIDE across corpus for portfolio view—not duplicate of per-CVE drawer sections.",
        },
        {
            "category": "performance",
            "q": "Is ARCH graph computed on every request?",
            "a": "Committed generated corpus loaded from disk; drift check is explicit admin/CI action. Runtime CVE queries use normal <code>db/</code> paths—not graph generation.",
        },
        {
            "category": "failure",
            "q": "What if corpus and code disagree?",
            "a": "Drift check fails CI/admin action; operators regenerate and commit. PRODUCT_STATUS and code win over stale graph labels in interviews.",
        },
        {
            "category": "overview",
            "q": "What is Security posture vs Security admin panel?",
            "a": "Posture (PM-4a): read-only architecture/risk transparency for analysts. Admin Security: operator warnings (rate limits, cookies, wallboard token), config, corpus tools—editable operator surface.",
        },
        {
            "category": "integration",
            "q": "How does ARCH link to scheduler jobs in interviews?",
            "a": "Graph nodes like <code>job:nvd_incremental_sync</code> edge to <code>table:cves</code> and <code>ext:nvd</code>—useful to explain ingest blast radius without reading all of <code>scheduler.py</code>.",
        },
    ],
}

# Insert secarch after security, before backend-db
SECARCH_INSERT_AFTER = "iv-security"


def merge_gap_questions(segments: list[dict]) -> list[dict]:
    out: list[dict] = []
    for seg in segments:
        slug = seg["slug"]
        if slug == SECARCH_INSERT_AFTER:
            out.append(seg)
            out.append(dict(SECARCH_SEGMENT))
            continue
        row = dict(seg)
        extra = GAP_BY_SLUG.get(slug, [])
        if extra:
            row["questions"] = list(row.get("questions", [])) + extra
        out.append(row)
    return out
