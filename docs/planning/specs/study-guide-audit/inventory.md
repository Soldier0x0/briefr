# Study guide file inventory

_Regenerated 2026-07-19 by `scripts/audit_study_guide.py`. Do not hand-edit; re-run the script._

| Status | Count |
|--------|------:|
| `covered` | 218 |
| `weak` | 67 |
| `gap` | 399 |
| `orphan_mention` | 1 |
| `out_of_scope` | 1 |

| Path | Status | Chapters | Evidence / notes |
|------|--------|----------|------------------|
| `backend/ai/__init__.py` | `weak` | `api-routers`, `arch-ai-restraint`, `ie-ml`, `ie-ml-providers` | sibling/dir coverage under backend/ai/; File never named; only directory-level association |
| `backend/ai/gemini_client.py` | `weak` | `api-routers`, `arch-ai-restraint`, `ie-ml`, `ie-ml-providers` | sibling/dir coverage under backend/ai/; File never named; only directory-level association |
| `backend/ai/groq_config.py` | `weak` | `api-routers`, `arch-ai-restraint`, `ie-ml`, `ie-ml-providers` | sibling/dir coverage under backend/ai/; File never named; only directory-level association |
| `backend/ai/llm_pacing.py` | `covered` | `ie-ml-providers` | exact path mention in chapter body/chips |
| `backend/ai/llm_payload.py` | `weak` | `api-routers`, `arch-ai-restraint`, `ie-ml`, `ie-ml-providers` | sibling/dir coverage under backend/ai/; File never named; only directory-level association |
| `backend/ai/llm_router.py` | `covered` | `arch-ai-restraint`, `ie-ml` | exact path mention in chapter body/chips |
| `backend/ai/llm_session.py` | `weak` | `api-routers`, `arch-ai-restraint`, `ie-ml`, `ie-ml-providers` | sibling/dir coverage under backend/ai/; File never named; only directory-level association |
| `backend/ai/model_catalog.py` | `covered` | `ie-ml-providers` | exact path mention in chapter body/chips |
| `backend/ai/openai_chat.py` | `weak` | `api-routers`, `arch-ai-restraint`, `ie-ml`, `ie-ml-providers` | sibling/dir coverage under backend/ai/; File never named; only directory-level association |
| `backend/ai/operations_admin.py` | `weak` | `api-routers`, `arch-ai-restraint`, `ie-ml`, `ie-ml-providers` | sibling/dir coverage under backend/ai/; File never named; only directory-level association |
| `backend/ai/operations_recorder.py` | `covered` | `ie-ml-providers` | exact path mention in chapter body/chips |
| `backend/ai/quota.py` | `covered` | `ie-ml-providers` | exact path mention in chapter body/chips |
| `backend/ai/summary.py` | `covered` | `api-routers`, `ie-ml-providers` | exact path mention in chapter body/chips |
| `backend/alembic/env.py` | `covered` | `be-alembic` | exact path mention in chapter body/chips |
| `backend/alembic/versions/001_initial_schema.py` | `covered` | `be-alembic` | exact path mention in chapter body/chips |
| `backend/alembic/versions/002_users_sessions.py` | `covered` | `be-alembic` | exact path mention in chapter body/chips |
| `backend/alembic/versions/003_users_email_to_username.py` | `covered` | `be-alembic` | exact path mention in chapter body/chips |
| `backend/alembic/versions/004_sqlite_schema_parity.py` | `covered` | `be-alembic` | exact path mention in chapter body/chips |
| `backend/alembic/versions/005_epss_percentile.py` | `covered` | `be-alembic` | exact path mention in chapter body/chips |
| `backend/alembic/versions/006_user_preferences.py` | `covered` | `be-alembic` | exact path mention in chapter body/chips |
| `backend/alembic/versions/007_user_display_prefs.py` | `covered` | `be-alembic` | exact path mention in chapter body/chips |
| `backend/alembic/versions/008_remember_profile.py` | `covered` | `be-alembic` | exact path mention in chapter body/chips |
| `backend/alembic/versions/009_app_settings.py` | `covered` | `be-alembic` | exact path mention in chapter body/chips |
| `backend/alembic/versions/010_detection_backlog.py` | `covered` | `be-alembic` | exact path mention in chapter body/chips |
| `backend/alembic/versions/011_ioc_watchlist.py` | `covered` | `be-alembic` | exact path mention in chapter body/chips |
| `backend/alembic/versions/012_cve_trgm_search.py` | `covered` | `be-alembic` | exact path mention in chapter body/chips |
| `backend/alembic/versions/013_webhook_destination_dedupe.py` | `covered` | `be-alembic` | exact path mention in chapter body/chips |
| `backend/alembic/versions/014_ai_operations.py` | `covered` | `be-alembic` | exact path mention in chapter body/chips |
| `backend/alembic/versions/015_user_notifications.py` | `covered` | `be-alembic` | exact path mention in chapter body/chips |
| `backend/alembic/versions/016_drop_correlation_infra.py` | `covered` | `be-alembic` | exact path mention in chapter body/chips |
| `backend/alembic/versions/017_ioc_degree.py` | `covered` | `be-alembic` | exact path mention in chapter body/chips |
| `backend/alembic/versions/018_otx_pulse_iocs_observed_at.py` | `covered` | `be-alembic` | exact path mention in chapter body/chips |
| `backend/alembic/versions/019_pulse_families.py` | `covered` | `be-alembic` | exact path mention in chapter body/chips |
| `backend/alembic/versions/020_correlation_feedback.py` | `covered` | `be-alembic` | exact path mention in chapter body/chips |
| `backend/alembic/versions/021_correlation_metrics.py` | `covered` | `be-alembic` | exact path mention in chapter body/chips |
| `backend/alembic/versions/022_idx_cves_modified.py` | `covered` | `be-alembic` | exact path mention in chapter body/chips |
| `backend/alembic/versions/023_resource_metrics.py` | `covered` | `be-alembic` | exact path mention in chapter body/chips |
| `backend/alembic/versions/024_audit_log_metadata.py` | `covered` | `be-alembic` | exact path mention in chapter body/chips |
| `backend/alembic/versions/025_correlation_cve_snapshot.py` | `covered` | `be-alembic` | exact path mention in chapter body/chips |
| `backend/alembic/versions/026_cve_detected_at_tz.py` | `covered` | `be-alembic` | exact path mention in chapter body/chips |
| `backend/alembic/versions/027_alembic_version_num_widen.py` | `covered` | `be-alembic` | exact path mention in chapter body/chips |
| `backend/alembic/versions/028_procrastinate_schema.py` | `covered` | `be-alembic` | exact path mention in chapter body/chips |
| `backend/alembic/versions/029_api_call_events.py` | `covered` | `be-alembic` | exact path mention in chapter body/chips |
| `backend/alembic/versions/030_software_catalog.py` | `covered` | `be-alembic` | exact path mention in chapter body/chips |
| `backend/alembic/versions/031_stack_backfill.py` | `covered` | `be-alembic` | exact path mention in chapter body/chips |
| `backend/alembic/versions/032_embeddings_pgvector.py` | `covered` | `be-alembic` | exact path mention in chapter body/chips |
| `backend/alembic/versions/033_search_api_tokens.py` | `covered` | `be-alembic` | exact path mention in chapter body/chips |
| `backend/alembic.ini` | `gap` | — | ; No study-guide ownership found |
| `backend/api_metering.py` | `gap` | — | ; No study-guide ownership found |
| `backend/api_queue.py` | `covered` | `in-queue` | exact path mention in chapter body/chips |
| `backend/api_queue_operations.py` | `gap` | — | ; No study-guide ownership found |
| `backend/auth/__init__.py` | `weak` | `be-auth` | sibling/dir coverage under backend/auth/; File never named; only directory-level association |
| `backend/auth/passwords.py` | `covered` | `be-auth` | exact path mention in chapter body/chips |
| `backend/auth/repo.py` | `covered` | `be-auth` | exact path mention in chapter body/chips |
| `backend/auth/tokens.py` | `covered` | `be-auth` | exact path mention in chapter body/chips |
| `backend/auth/usernames.py` | `covered` | `be-auth` | exact path mention in chapter body/chips |
| `backend/auth_middleware.py` | `covered` | `be-auth` | exact path mention in chapter body/chips |
| `backend/backup/__init__.py` | `weak` | `api-ops` | sibling/dir coverage under backend/backup/; File never named; only directory-level association |
| `backend/backup/__main__.py` | `covered` | `api-ops` | exact path mention in chapter body/chips |
| `backend/backup/manager.py` | `covered` | `api-ops` | exact path mention in chapter body/chips |
| `backend/backup/postgres_util.py` | `covered` | `api-ops` | exact path mention in chapter body/chips |
| `backend/brief/__init__.py` | `weak` | `api-ops`, `ie-brief` | sibling/dir coverage under backend/brief/; File never named; only directory-level association |
| `backend/brief/service.py` | `covered` | `api-ops`, `ie-brief` | exact path mention in chapter body/chips |
| `backend/config_schema.py` | `covered` | `be-config` | exact path mention in chapter body/chips |
| `backend/correlation/__init__.py` | `covered` | `ie-correlation` | exact path mention in chapter body/chips |
| `backend/correlation/attribution.py` | `covered` | `ie-correlation` | exact path mention in chapter body/chips |
| `backend/correlation/campaigns.py` | `covered` | `be-data`, `ie-correlation` | exact path mention in chapter body/chips |
| `backend/correlation/clusters.py` | `covered` | `ie-correlation` | exact path mention in chapter body/chips |
| `backend/correlation/confidence.py` | `covered` | `ie-correlation` | exact path mention in chapter body/chips |
| `backend/correlation/config.py` | `covered` | `be-data`, `ie-correlation` | exact path mention in chapter body/chips |
| `backend/correlation/confirm.py` | `covered` | `ie-correlation` | exact path mention in chapter body/chips |
| `backend/correlation/copy.py` | `covered` | `ie-correlation` | exact path mention in chapter body/chips |
| `backend/correlation/engine.py` | `covered` | `api-webhooks`, `ie-correlation`, `system-design` | exact path mention in chapter body/chips |
| `backend/correlation/feedback.py` | `covered` | `ie-correlation` | exact path mention in chapter body/chips |
| `backend/correlation/freshness.py` | `covered` | `ie-correlation` | exact path mention in chapter body/chips |
| `backend/correlation/hub_suppress.py` | `covered` | `ie-correlation` | exact path mention in chapter body/chips |
| `backend/correlation/ioc_graph.py` | `covered` | `ie-correlation` | exact path mention in chapter body/chips |
| `backend/correlation/ioc_normalize.py` | `covered` | `ie-correlation` | exact path mention in chapter body/chips |
| `backend/correlation/lifecycle.py` | `covered` | `ie-correlation` | exact path mention in chapter body/chips |
| `backend/correlation/local.py` | `covered` | `ie-correlation` | exact path mention in chapter body/chips |
| `backend/correlation/metrics.py` | `covered` | `be-data`, `ie-correlation` | exact path mention in chapter body/chips |
| `backend/correlation/priority.py` | `covered` | `ie-correlation`, `ie-scoring` | exact path mention in chapter body/chips |
| `backend/correlation/pulse_families.py` | `covered` | `ie-correlation` | exact path mention in chapter body/chips |
| `backend/correlation/status.py` | `covered` | `ie-correlation` | exact path mention in chapter body/chips |
| `backend/correlation/suppressions.py` | `covered` | `ie-correlation` | exact path mention in chapter body/chips |
| `backend/correlation/threatfox_corroboration.py` | `covered` | `ie-correlation` | exact path mention in chapter body/chips |
| `backend/database.py` | `covered` | `be-shim` | exact path mention in chapter body/chips |
| `backend/db/__init__.py` | `covered` | `be-data`, `system-design` | exact path mention in chapter body/chips |
| `backend/db/ai_operations.py` | `covered` | `be-data`, `system-design` | exact path mention in chapter body/chips |
| `backend/db/api_metering.py` | `covered` | `api-scripts`, `be-data`, `system-design` | exact path mention in chapter body/chips |
| `backend/db/app_settings.py` | `covered` | `be-data`, `system-design` | exact path mention in chapter body/chips |
| `backend/db/cache.py` | `covered` | `be-data`, `system-design` | exact path mention in chapter body/chips |
| `backend/db/cache_retention.py` | `covered` | `be-data`, `system-design` | exact path mention in chapter body/chips |
| `backend/db/config.py` | `covered` | `be-data`, `be-shim`, `system-design` | exact path mention in chapter body/chips |
| `backend/db/connection.py` | `covered` | `be-data`, `be-shim`, `system-design` | exact path mention in chapter body/chips |
| `backend/db/correlation.py` | `covered` | `be-data`, `system-design` | exact path mention in chapter body/chips |
| `backend/db/cve.py` | `covered` | `be-data`, `system-design` | exact path mention in chapter body/chips |
| `backend/db/embeddings_pgvector.py` | `covered` | `be-data`, `system-design` | exact path mention in chapter body/chips |
| `backend/db/embeddings_search.py` | `covered` | `be-data`, `system-design` | exact path mention in chapter body/chips |
| `backend/db/embeddings_store.py` | `covered` | `be-data`, `system-design` | exact path mention in chapter body/chips |
| `backend/db/enrichment.py` | `covered` | `be-data`, `system-design` | exact path mention in chapter body/chips |
| `backend/db/errors.py` | `covered` | `be-data`, `system-design` | exact path mention in chapter body/chips |
| `backend/db/explorer.py` | `covered` | `be-data`, `system-design` | exact path mention in chapter body/chips |
| `backend/db/explorer_registry.py` | `covered` | `be-data`, `system-design` | exact path mention in chapter body/chips |
| `backend/db/init.py` | `covered` | `be-alembic`, `be-data`, `system-design` | exact path mention in chapter body/chips |
| `backend/db/integrity.py` | `covered` | `be-data`, `system-design` | exact path mention in chapter body/chips |
| `backend/db/ioc_watchlist.py` | `covered` | `be-data`, `system-design` | exact path mention in chapter body/chips |
| `backend/db/metadata.py` | `covered` | `be-data`, `system-design` | exact path mention in chapter body/chips |
| `backend/db/outbound_jobs.py` | `covered` | `be-data`, `system-design` | exact path mention in chapter body/chips |
| `backend/db/pg_adapt.py` | `covered` | `be-data`, `system-design` | exact path mention in chapter body/chips |
| `backend/db/resource_metrics.py` | `covered` | `be-data`, `system-design` | exact path mention in chapter body/chips |
| `backend/db/search_tokens.py` | `covered` | `be-data`, `system-design` | exact path mention in chapter body/chips |
| `backend/db/software_catalog.py` | `covered` | `be-data`, `system-design` | exact path mention in chapter body/chips |
| `backend/db/stack_backfill.py` | `covered` | `be-data`, `system-design` | exact path mention in chapter body/chips |
| `backend/db/sync_state.py` | `covered` | `be-data`, `system-design` | exact path mention in chapter body/chips |
| `backend/db/threatfox.py` | `covered` | `be-data`, `system-design` | exact path mention in chapter body/chips |
| `backend/db/timeutil.py` | `covered` | `be-data`, `system-design` | exact path mention in chapter body/chips |
| `backend/db/types.py` | `covered` | `be-data`, `system-design` | exact path mention in chapter body/chips |
| `backend/db/user_notifications.py` | `covered` | `be-data`, `system-design` | exact path mention in chapter body/chips |
| `backend/db/watchlist.py` | `covered` | `be-data`, `system-design` | exact path mention in chapter body/chips |
| `backend/db/webhooks.py` | `covered` | `be-data`, `system-design` | exact path mention in chapter body/chips |
| `backend/dependencies.py` | `covered` | `be-bootstrap` | exact path mention in chapter body/chips |
| `backend/destructive_actions.py` | `covered` | `api-scripts` | exact path mention in chapter body/chips |
| `backend/detection/__init__.py` | `weak` | `ie-detection`, `in-jobs` | sibling/dir coverage under backend/detection/; File never named; only directory-level association |
| `backend/detection/artifact_extract.py` | `weak` | `ie-detection`, `in-jobs` | sibling/dir coverage under backend/detection/; File never named; only directory-level association |
| `backend/detection/backlog.py` | `covered` | `ie-detection` | exact path mention in chapter body/chips |
| `backend/detection/class_queries.py` | `weak` | `ie-detection`, `in-jobs` | sibling/dir coverage under backend/detection/; File never named; only directory-level association |
| `backend/detection/class_router.py` | `covered` | `ie-detection` | exact path mention in chapter body/chips |
| `backend/detection/composer.py` | `covered` | `ie-detection` | exact path mention in chapter body/chips |
| `backend/detection/context.py` | `covered` | `in-jobs` | exact path mention in chapter body/chips |
| `backend/detection/context_llm_sync.py` | `weak` | `ie-detection`, `in-jobs` | sibling/dir coverage under backend/detection/; File never named; only directory-level association |
| `backend/detection/context_nuclei_sync.py` | `weak` | `ie-detection`, `in-jobs` | sibling/dir coverage under backend/detection/; File never named; only directory-level association |
| `backend/detection/context_sync.py` | `weak` | `ie-detection`, `in-jobs` | sibling/dir coverage under backend/detection/; File never named; only directory-level association |
| `backend/detection/nuclei_parser.py` | `weak` | `ie-detection`, `in-jobs` | sibling/dir coverage under backend/detection/; File never named; only directory-level association |
| `backend/detection/rule_sources.py` | `weak` | `ie-detection`, `in-jobs` | sibling/dir coverage under backend/detection/; File never named; only directory-level association |
| `backend/detection/siem_queries.py` | `weak` | `ie-detection`, `in-jobs` | sibling/dir coverage under backend/detection/; File never named; only directory-level association |
| `backend/detection/sigma_generator.py` | `covered` | `ie-detection` | exact path mention in chapter body/chips |
| `backend/detection/yara_generator.py` | `weak` | `ie-detection`, `in-jobs` | sibling/dir coverage under backend/detection/; File never named; only directory-level association |
| `backend/diagnostics/__init__.py` | `weak` | `api-ops` | sibling/dir coverage under backend/diagnostics/; File never named; only directory-level association |
| `backend/diagnostics/support_pack.py` | `covered` | `api-ops` | exact path mention in chapter body/chips |
| `backend/enrichment/__init__.py` | `covered` | `ie-ml` | exact path mention in chapter body/chips |
| `backend/enrichment/cve.py` | `covered` | `api-proof`, `ie-ml` | exact path mention in chapter body/chips |
| `backend/enrichment/domain_validation.py` | `covered` | `api-proof`, `ie-ml` | exact path mention in chapter body/chips |
| `backend/enrichment/ioc.py` | `covered` | `api-proof`, `ie-ml` | exact path mention in chapter body/chips |
| `backend/feeds/__init__.py` | `weak` | `in-feeds` | sibling/dir coverage under backend/feeds/; File never named; only directory-level association |
| `backend/feeds/ai_context.py` | `weak` | `in-feeds` | sibling/dir coverage under backend/feeds/; File never named; only directory-level association |
| `backend/feeds/atlas.py` | `weak` | `in-feeds` | sibling/dir coverage under backend/feeds/; File never named; only directory-level association |
| `backend/feeds/case_study_feed.py` | `weak` | `in-feeds` | sibling/dir coverage under backend/feeds/; File never named; only directory-level association |
| `backend/feeds/cpe_catalog.py` | `weak` | `in-feeds` | sibling/dir coverage under backend/feeds/; File never named; only directory-level association |
| `backend/feeds/cve_record_v5.py` | `weak` | `in-feeds` | sibling/dir coverage under backend/feeds/; File never named; only directory-level association |
| `backend/feeds/cvelistv5.py` | `covered` | `in-feeds` | exact path mention in chapter body/chips |
| `backend/feeds/epss.py` | `covered` | `in-feeds` | exact path mention in chapter body/chips |
| `backend/feeds/errors.py` | `weak` | `in-feeds` | sibling/dir coverage under backend/feeds/; File never named; only directory-level association |
| `backend/feeds/exploit_common.py` | `weak` | `in-feeds` | sibling/dir coverage under backend/feeds/; File never named; only directory-level association |
| `backend/feeds/exploit_sync.py` | `weak` | `in-feeds` | sibling/dir coverage under backend/feeds/; File never named; only directory-level association |
| `backend/feeds/exploitdb.py` | `weak` | `in-feeds` | sibling/dir coverage under backend/feeds/; File never named; only directory-level association |
| `backend/feeds/extended.py` | `weak` | `in-feeds` | sibling/dir coverage under backend/feeds/; File never named; only directory-level association |
| `backend/feeds/file_identity.py` | `weak` | `in-feeds` | sibling/dir coverage under backend/feeds/; File never named; only directory-level association |
| `backend/feeds/github_helpers.py` | `weak` | `in-feeds` | sibling/dir coverage under backend/feeds/; File never named; only directory-level association |
| `backend/feeds/incident_news.py` | `weak` | `in-feeds` | sibling/dir coverage under backend/feeds/; File never named; only directory-level association |
| `backend/feeds/incident_sources.py` | `weak` | `in-feeds` | sibling/dir coverage under backend/feeds/; File never named; only directory-level association |
| `backend/feeds/kev.py` | `covered` | `in-feeds` | exact path mention in chapter body/chips |
| `backend/feeds/metasploit_modules.py` | `weak` | `in-feeds` | sibling/dir coverage under backend/feeds/; File never named; only directory-level association |
| `backend/feeds/mitre.py` | `weak` | `in-feeds` | sibling/dir coverage under backend/feeds/; File never named; only directory-level association |
| `backend/feeds/nuclei_index.py` | `weak` | `in-feeds` | sibling/dir coverage under backend/feeds/; File never named; only directory-level association |
| `backend/feeds/nvd.py` | `covered` | `in-feeds` | exact path mention in chapter body/chips |
| `backend/feeds/osv.py` | `weak` | `in-feeds` | sibling/dir coverage under backend/feeds/; File never named; only directory-level association |
| `backend/feeds/otx.py` | `weak` | `in-feeds` | sibling/dir coverage under backend/feeds/; File never named; only directory-level association |
| `backend/feeds/otx_continuous.py` | `weak` | `in-feeds` | sibling/dir coverage under backend/feeds/; File never named; only directory-level association |
| `backend/feeds/poc_github.py` | `weak` | `in-feeds` | sibling/dir coverage under backend/feeds/; File never named; only directory-level association |
| `backend/feeds/threatfox.py` | `weak` | `in-feeds` | sibling/dir coverage under backend/feeds/; File never named; only directory-level association |
| `backend/feeds/vulncheck_kev.py` | `weak` | `in-feeds` | sibling/dir coverage under backend/feeds/; File never named; only directory-level association |
| `backend/feeds/vulnrichment.py` | `weak` | `in-feeds` | sibling/dir coverage under backend/feeds/; File never named; only directory-level association |
| `backend/intel/__init__.py` | `weak` | `ie-threatmodel` | sibling/dir coverage under backend/intel/; File never named; only directory-level association |
| `backend/intel/provenance.py` | `covered` | `ie-threatmodel` | exact path mention in chapter body/chips |
| `backend/ioc/__init__.py` | `weak` | `ie-threatmodel` | sibling/dir coverage under backend/ioc/; File never named; only directory-level association |
| `backend/ioc/retro_match.py` | `covered` | `ie-threatmodel` | exact path mention in chapter body/chips |
| `backend/jobs/__init__.py` | `weak` | `in-jobs` | sibling/dir coverage under backend/jobs/; File never named; only directory-level association |
| `backend/jobs/app.py` | `covered` | `in-jobs` | exact path mention in chapter body/chips |
| `backend/jobs/context.py` | `covered` | `in-jobs` | exact path mention in chapter body/chips |
| `backend/jobs/tasks.py` | `covered` | `in-jobs` | exact path mention in chapter body/chips |
| `backend/jobs/worker.py` | `covered` | `in-jobs` | exact path mention in chapter body/chips |
| `backend/main.py` | `covered` | `be-bootstrap` | exact path mention in chapter body/chips |
| `backend/matching/__init__.py` | `weak` | `ie-matching` | sibling/dir coverage under backend/matching/; File never named; only directory-level association |
| `backend/matching/cpe.py` | `covered` | `ie-matching` | exact path mention in chapter body/chips |
| `backend/metrics/__init__.py` | `weak` | `api-ops`, `api-scripts` | sibling/dir coverage under backend/metrics/; File never named; only directory-level association |
| `backend/metrics/request_counter.py` | `covered` | `api-ops`, `api-scripts` | exact path mention in chapter body/chips |
| `backend/migration/__init__.py` | `weak` | `api-ops` | sibling/dir coverage under backend/migration/; File never named; only directory-level association |
| `backend/migration/sqlite_to_postgres.py` | `covered` | `api-ops` | exact path mention in chapter body/chips |
| `backend/ml/__init__.py` | `weak` | `arch-ai-restraint`, `arch-resources`, `ie-ml` | sibling/dir coverage under backend/ml/; File never named; only directory-level association |
| `backend/ml/embeddings.py` | `covered` | `arch-ai-restraint`, `arch-resources`, `ie-ml` | exact path mention in chapter body/chips |
| `backend/ml/product_extraction.py` | `covered` | `ie-ml` | exact path mention in chapter body/chips |
| `backend/monitoring/__init__.py` | `weak` | `api-ops` | sibling/dir coverage under backend/monitoring/; File never named; only directory-level association |
| `backend/monitoring/api_key_health.py` | `covered` | `api-ops` | exact path mention in chapter body/chips |
| `backend/monitoring/notifications.py` | `covered` | `api-ops` | exact path mention in chapter body/chips |
| `backend/notifications/emit.py` | `covered` | `api-usersettings` | exact path mention in chapter body/chips |
| `backend/onboarding/__init__.py` | `weak` | `api-usersettings` | sibling/dir coverage under backend/onboarding/; File never named; only directory-level association |
| `backend/onboarding/checklist.py` | `covered` | `api-usersettings` | exact path mention in chapter body/chips |
| `backend/operator_settings.py` | `gap` | — | ; No study-guide ownership found |
| `backend/preferences/display_validate.py` | `covered` | `api-usersettings` | exact path mention in chapter body/chips |
| `backend/preferences/repo.py` | `covered` | `api-usersettings` | exact path mention in chapter body/chips |
| `backend/preferences/validate.py` | `covered` | `api-usersettings` | exact path mention in chapter body/chips |
| `backend/proof/__init__.py` | `weak` | `api-proof` | sibling/dir coverage under backend/proof/; File never named; only directory-level association |
| `backend/proof/bench.py` | `covered` | `api-proof` | exact path mention in chapter body/chips |
| `backend/pytest.ini` | `gap` | — | ; No study-guide ownership found |
| `backend/rate_limit.py` | `covered` | `arch-resources`, `be-ratelimit` | exact path mention in chapter body/chips |
| `backend/rate_limit_store.py` | `covered` | `be-ratelimit` | exact path mention in chapter body/chips |
| `backend/read_cache.py` | `gap` | — | ; No study-guide ownership found |
| `backend/redact.py` | `covered` | `be-logging` | exact path mention in chapter body/chips |
| `backend/resilient_client.py` | `covered` | `in-queue` | exact path mention in chapter body/chips |
| `backend/resource_collector.py` | `gap` | — | ; No study-guide ownership found |
| `backend/routers/__init__.py` | `covered` | `system-design` | exact path mention in chapter body/chips |
| `backend/routers/_validators.py` | `covered` | `system-design` | exact path mention in chapter body/chips |
| `backend/routers/admin.py` | `covered` | `api-routers`, `api-scripts`, `be-config`, `in-scheduler`, `system-design` | exact path mention in chapter body/chips |
| `backend/routers/atlas.py` | `covered` | `system-design` | exact path mention in chapter body/chips |
| `backend/routers/auth.py` | `covered` | `api-routers`, `system-design` | exact path mention in chapter body/chips |
| `backend/routers/brief.py` | `covered` | `system-design` | exact path mention in chapter body/chips |
| `backend/routers/config.py` | `covered` | `system-design` | exact path mention in chapter body/chips |
| `backend/routers/correlation.py` | `covered` | `system-design` | exact path mention in chapter body/chips |
| `backend/routers/cves.py` | `covered` | `api-routers`, `api-secarch`, `arch-connectivity`, `system-design` | exact path mention in chapter body/chips |
| `backend/routers/detection_backlog.py` | `covered` | `system-design` | exact path mention in chapter body/chips |
| `backend/routers/forge.py` | `covered` | `api-secarch`, `system-design` | exact path mention in chapter body/chips |
| `backend/routers/health.py` | `covered` | `system-design` | exact path mention in chapter body/chips |
| `backend/routers/ioc.py` | `covered` | `system-design` | exact path mention in chapter body/chips |
| `backend/routers/me.py` | `covered` | `fe-state`, `system-design` | exact path mention in chapter body/chips |
| `backend/routers/meta.py` | `covered` | `system-design` | exact path mention in chapter body/chips |
| `backend/routers/notifications_me.py` | `covered` | `system-design` | exact path mention in chapter body/chips |
| `backend/routers/proof.py` | `covered` | `system-design` | exact path mention in chapter body/chips |
| `backend/routers/refresh.py` | `covered` | `system-design` | exact path mention in chapter body/chips |
| `backend/routers/search.py` | `covered` | `system-design` | exact path mention in chapter body/chips |
| `backend/routers/stack_catalog.py` | `covered` | `system-design` | exact path mention in chapter body/chips |
| `backend/routers/threat_model.py` | `covered` | `system-design` | exact path mention in chapter body/chips |
| `backend/routers/wallboard.py` | `covered` | `system-design` | exact path mention in chapter body/chips |
| `backend/routers/watchlist.py` | `covered` | `system-design` | exact path mention in chapter body/chips |
| `backend/scheduler.py` | `covered` | `in-scheduler` | exact path mention in chapter body/chips |
| `backend/scheduler_locks.py` | `covered` | `in-scheduler` | exact path mention in chapter body/chips |
| `backend/scoring/__init__.py` | `weak` | `api-routers`, `arch-ai-restraint`, `ie-correlation`, `ie-matching`, `ie-scoring` | sibling/dir coverage under backend/scoring/; File never named; only directory-level association |
| `backend/scoring/asset_match.py` | `covered` | `ie-matching` | exact path mention in chapter body/chips |
| `backend/scoring/environment.py` | `covered` | `ie-scoring` | exact path mention in chapter body/chips |
| `backend/scoring/priority.py` | `covered` | `ie-scoring` | exact path mention in chapter body/chips |
| `backend/scoring/risk.py` | `covered` | `api-routers`, `arch-ai-restraint`, `ie-correlation`, `ie-scoring` | exact path mention in chapter body/chips |
| `backend/scoring/threat.py` | `covered` | `ie-scoring` | exact path mention in chapter body/chips |
| `backend/scripts/backfill_poc.py` | `covered` | `api-scripts` | exact path mention in chapter body/chips |
| `backend/scripts/create_user.py` | `covered` | `api-scripts` | exact path mention in chapter body/chips |
| `backend/scripts/delete_user.py` | `weak` | `api-scripts` | sibling/dir coverage under backend/scripts/; File never named; only directory-level association |
| `backend/scripts/sync_env.py` | `covered` | `api-scripts` | exact path mention in chapter body/chips |
| `backend/security_architecture/__init__.py` | `covered` | `api-secarch` | exact path mention in chapter body/chips |
| `backend/security_architecture/corpus/abuse_cases.yaml` | `gap` | — | ; No study-guide ownership found |
| `backend/security_architecture/corpus/api_inventory.yaml` | `gap` | — | ; No study-guide ownership found |
| `backend/security_architecture/corpus/components.yaml` | `gap` | — | ; No study-guide ownership found |
| `backend/security_architecture/corpus/controls.yaml` | `gap` | — | ; No study-guide ownership found |
| `backend/security_architecture/corpus/db_tables.yaml` | `gap` | — | ; No study-guide ownership found |
| `backend/security_architecture/corpus/graphs/architecture.json` | `gap` | — | ; No study-guide ownership found |
| `backend/security_architecture/corpus/manifest.yaml` | `gap` | — | ; No study-guide ownership found |
| `backend/security_architecture/corpus/reviews.yaml` | `gap` | — | ; No study-guide ownership found |
| `backend/security_architecture/corpus/risks.yaml` | `gap` | — | ; No study-guide ownership found |
| `backend/security_architecture/corpus/scheduler_jobs.yaml` | `gap` | — | ; No study-guide ownership found |
| `backend/security_architecture/corpus/security_decisions.yaml` | `gap` | — | ; No study-guide ownership found |
| `backend/security_architecture/corpus/self_stack.yaml` | `gap` | — | ; No study-guide ownership found |
| `backend/security_architecture/corpus/threat_scenarios.yaml` | `gap` | — | ; No study-guide ownership found |
| `backend/security_architecture/corpus/trust_boundaries.yaml` | `gap` | — | ; No study-guide ownership found |
| `backend/security_architecture/corpus_drift.py` | `covered` | `api-secarch` | exact path mention in chapter body/chips |
| `backend/security_architecture/corpus_loader.py` | `covered` | `api-secarch` | exact path mention in chapter body/chips |
| `backend/security_architecture/frameworks/__init__.py` | `weak` | `api-secarch` | sibling/dir coverage under backend/security_architecture/frameworks/; File never named; only directory-level association |
| `backend/security_architecture/frameworks/aggregate.py` | `covered` | `api-secarch` | exact path mention in chapter body/chips |
| `backend/security_architecture/frameworks/reference.py` | `covered` | `api-secarch` | exact path mention in chapter body/chips |
| `backend/security_architecture/frameworks/scope.py` | `covered` | `api-secarch` | exact path mention in chapter body/chips |
| `backend/security_architecture/graphs.py` | `covered` | `api-secarch` | exact path mention in chapter body/chips |
| `backend/security_architecture/merge.py` | `covered` | `api-secarch` | exact path mention in chapter body/chips |
| `backend/security_architecture/routers/__init__.py` | `weak` | `api-secarch` | sibling/dir coverage under backend/security_architecture/routers/; File never named; only directory-level association |
| `backend/security_architecture/routers/security_architecture.py` | `covered` | `api-secarch` | exact path mention in chapter body/chips |
| `backend/services/__init__.py` | `weak` | `api-proof`, `in-jobs` | sibling/dir coverage under backend/services/; File never named; only directory-level association |
| `backend/services/retrieval_health.py` | `weak` | `api-proof`, `in-jobs` | sibling/dir coverage under backend/services/; File never named; only directory-level association |
| `backend/services/semantic_search.py` | `covered` | `api-proof` | exact path mention in chapter body/chips |
| `backend/services/stack_backfill_worker.py` | `covered` | `api-proof`, `in-jobs` | exact path mention in chapter body/chips |
| `backend/settings.py` | `covered` | `be-config` | exact path mention in chapter body/chips |
| `backend/settings_crypto.py` | `covered` | `be-config` | exact path mention in chapter body/chips |
| `backend/source_rate_limits.py` | `covered` | `in-queue` | exact path mention in chapter body/chips |
| `backend/storage_metrics.py` | `gap` | — | ; No study-guide ownership found |
| `backend/structured_logging.py` | `covered` | `be-logging` | exact path mention in chapter body/chips |
| `backend/task_registry.py` | `covered` | `api-scripts` | exact path mention in chapter body/chips |
| `backend/templates/__init__.py` | `weak` | `api-proof` | sibling/dir coverage under backend/templates/; File never named; only directory-level association |
| `backend/templates/intelligence.py` | `covered` | `api-proof` | exact path mention in chapter body/chips |
| `backend/threat_model/__init__.py` | `weak` | `ie-threatmodel` | sibling/dir coverage under backend/threat_model/; File never named; only directory-level association |
| `backend/threat_model/scenarios.py` | `covered` | `ie-threatmodel` | exact path mention in chapter body/chips |
| `backend/tracking.py` | `covered` | `api-scripts` | exact path mention in chapter body/chips |
| `backend/wallboard/__init__.py` | `weak` | `api-ops` | sibling/dir coverage under backend/wallboard/; File never named; only directory-level association |
| `backend/wallboard/service.py` | `covered` | `api-ops` | exact path mention in chapter body/chips |
| `backend/wallboard/session.py` | `weak` | `api-ops` | sibling/dir coverage under backend/wallboard/; File never named; only directory-level association |
| `backend/webhooks/__init__.py` | `weak` | `api-webhooks` | sibling/dir coverage under backend/webhooks/; File never named; only directory-level association |
| `backend/webhooks/alerts.py` | `covered` | `api-webhooks` | exact path mention in chapter body/chips |
| `backend/webhooks/destinations.py` | `covered` | `api-webhooks` | exact path mention in chapter body/chips |
| `backend/webhooks/engine.py` | `covered` | `api-webhooks` | exact path mention in chapter body/chips |
| `backend/webhooks/sender.py` | `covered` | `api-webhooks` | exact path mention in chapter body/chips |
| `backend/webhooks/ssrf.py` | `covered` | `api-webhooks` | exact path mention in chapter body/chips |
| `frontend/src/App.css` | `covered` | `fe-design` | exact path mention in chapter body/chips |
| `frontend/src/App.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/api.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/AboutModal.css` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/AboutModal.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/ApiQueueIndicator.css` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/ApiQueueIndicator.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/AppErrorBoundary.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/AssetProfileManage.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/AssetRememberToggle.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/AssetWarning.css` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/AssetWarning.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/AssetWizard.css` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/AssetWizard.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/BriefCharts.css` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/BriefCharts.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/CVECard.css` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/CVECard.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/CVEFeed.css` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/CVEFeed.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/CaseStudies.css` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/CaseStudies.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/CommandPalette.css` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/CommandPalette.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/ControlTooltip.css` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/ControlTooltip.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/CveDescriptionClamp.css` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/CveDescriptionClamp.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/DetailDrawer/CorrelationSuppressModal.css` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/DetailDrawer/CorrelationSuppressModal.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/DetailDrawer/DetectTab.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/DetailDrawer/IntelProvenanceLine.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/DetailDrawer/IntelTab.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/DetailDrawer/OverviewTab.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/DetailDrawer/RelatedTab.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/DetailDrawer/helpers.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/DetailDrawer/index.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/DetailDrawer.css` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/DigestModal.css` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/DigestModal.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/DrawerAtlasSection.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/ExplainTip.css` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/ExplainTip.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/FeedVisibleRange.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/FilterBar.css` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/FilterBar.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/Forge.css` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/Forge.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/Header.css` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/Header.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/HeaderClock.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/Hero.css` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/Hero.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/IOCLookup.css` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/IOCLookup.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/InvestigationPanel.css` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/InvestigationPanel.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/MorningBrief.css` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/MorningBrief.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/NotificationBell.css` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/NotificationBell.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/PdfExportModal.css` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/PdfExportModal.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/RequireAdmin.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/RequireAuth.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/ScrollToTop.css` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/ScrollToTop.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/SessionIdleWarning.css` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/SessionIdleWarning.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/SessionLockOverlay.css` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/SessionLockOverlay.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/SeverityLegend.css` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/SeverityLegend.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/ShortcutsPanel.css` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/ShortcutsPanel.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/Sidebar.css` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/Sidebar.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/StatsRow.css` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/StatsRow.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/TimeWindowPicker.css` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/TimeWindowPicker.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/TimelineHeatmap.css` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/TimelineHeatmap.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/Toast.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/ToolErrorBoundary.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/TutorialOverlay.css` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/TutorialOverlay.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/UserMenu.css` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/UserMenu.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/WhatChangedPanel.css` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/WhatChangedPanel.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/briefVendorChartRecharts.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/forge/BacklogView.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/forge/CampaignsView.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/forge/CoverageView.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/forge/HuntPackRail.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/forge/LibraryView.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/forge/ScenariosView.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/forge/mitreTacticOrder.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/forge/shared.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/timeWindowDateUtils.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/timeWindowDateUtils.test.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/ui/AlertDialog.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/ui/AsyncState.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/ui/AsyncState.test.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/ui/Badge.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/ui/Button.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/ui/Card.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/ui/ChartDataTable.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/ui/ChartShell.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/ui/Checkbox.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/ui/ConfirmModal.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/ui/DataGrid.css` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/ui/DataGrid.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/ui/DateTimePicker.css` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/ui/DateTimePicker.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/ui/DateTimeRangeField.css` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/ui/DateTimeRangeField.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/ui/DropdownMenu.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/ui/EmptyState.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/ui/ErrorState.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/ui/Modal.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/ui/Pill.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/ui/ReferenceTooltip.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/ui/Select.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/ui/Skeleton.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/ui/SkeletonStack.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/ui/Slider.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/ui/StatCard.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/ui/Switch.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/ui/Tabs.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/ui/Toast.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/ui/Tooltip.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/ui/Tooltip.test.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/ui/index.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/components/ui/ui.css` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/config/assetCatalog.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/config/caseStudySources.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/context/AssetProfileContext.jsx` | `covered` | `fe-react`, `fe-state` | exact path mention in chapter body/chips |
| `frontend/src/context/AuthContext.jsx` | `covered` | `fe-react`, `fe-state` | exact path mention in chapter body/chips |
| `frontend/src/context/InvestigationContext.jsx` | `covered` | `fe-state` | exact path mention in chapter body/chips |
| `frontend/src/hooks/useAsync.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/hooks/useInactivityTimeout.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/hooks/useModalLayer.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/hooks/useVisibilityAwareInterval.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/hooks/useWatchlist.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/main.jsx` | `covered` | `fe-react` | exact path mention in chapter body/chips |
| `frontend/src/pages/AdminPage.css` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/LegalPage.css` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/LegalPage.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/LoginPage.css` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/LoginPage.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/PrivacyPage.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/TermsPage.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/WallboardPage.css` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/WallboardPage.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/AdminPage.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/AiOperationsPage.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/AlertsPage.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/ApiKeyHealthPanel.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/ApiKeysPage.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/AuditLogPage.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/BackupsPage.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/ComingSoonPage.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/DatabasePage.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/DbExplorerPanel.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/DisplayPage.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/FeedHealthPage.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/IngestLogPage.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/OverviewPage.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/RateLimitPage.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/ResourcesPage.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/SchedulerPage.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/SearchTokensPanel.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/SecurityPage.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/SecurityPosturePage.css` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/SecurityPosturePage.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/SessionsPage.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/Sidebar.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/StatusBar.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/StoragePage.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/WatchlistPage.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/WebhookDestinationCard.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/WebhooksPage.css` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/WebhooksPage.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/adminFormFieldGate.test.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/adminJobAck.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/adminNav.test.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/adminUrlPageClearGate.test.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/catalog.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/circuitLabels.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/constants.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/formatters.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/formatters.test.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/intelStatus.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/jobActions.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/jobActions.test.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/jobStatus.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/needsAttention.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/needsAttention.test.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/rateLimits.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/resourceChartUtils.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/resourceChartUtils.test.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/resourcesChartsRecharts.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/shared/ActionProgress.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/shared/AdminBreadcrumbs.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/shared/AdminDataGrid.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/shared/AdminSkeletons.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/shared/AsyncSection.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/shared/ConfirmModal.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/shared/DangerZone.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/shared/DiffReviewModal.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/shared/ErrorBoundary.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/shared/GuardedPurgePanel.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/shared/HelpTip.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/shared/JobErrorsPanel.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/shared/JobTable.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/shared/NeedsAttentionPanel.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/shared/NotificationCenter.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/shared/OperationTracker.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/shared/OperatorSystemActions.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/shared/OpsCharts.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/shared/RestartBanner.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/shared/RunningJobsPanel.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/shared/StatCard.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/shared/StatusLegend.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/shared/ToggleSwitch.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/shared/adminListResponse.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/shared/backupChartUtils.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/shared/backupChartUtils.test.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/shared/opsChartsRecharts.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/toastCopy.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/admin/toastCopy.test.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/security-architecture/ContextRail.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/security-architecture/GlobalSearch.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/security-architecture/SecurityArchitecturePage.css` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/security-architecture/SecurityArchitecturePage.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/security-architecture/constants.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/security-architecture/sections/AbuseCasesSection.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/security-architecture/sections/ArchitectureGraphSection.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/security-architecture/sections/AttackSurfaceSection.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/security-architecture/sections/DecisionsSection.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/security-architecture/sections/FrameworkSection.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/security-architecture/sections/GenericSection.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/security-architecture/sections/MitreSection.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/security-architecture/sections/OverviewSection.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/security-architecture/sections/ReviewHistorySection.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/security-architecture/sections/RiskRegisterSection.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/security-architecture/sections/StaleRecordsSection.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/security-architecture/sections/ThreatScenariosSection.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/security-architecture/sections/TrustBoundariesSection.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/pages/security-architecture/shared/ArchDataGrid.jsx` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/scoring/riskScore.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/scoring/riskScore.test.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/styles/tokens.css` | `covered` | `fe-design` | exact path mention in chapter body/chips |
| `frontend/src/theme/light-theme.css` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/activeStateGate.test.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/adminLinks.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/adminMode.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/aiAssets.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/apiQueuePresentation.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/apiQueuePresentation.test.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/appLinks.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/archAnalystCleanupGate.test.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/archLayoutGate.test.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/archTabRemovalGate.test.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/architectureGraphGate.test.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/architectureGraphLayout.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/architectureGraphView.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/architectureGraphView.test.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/assetProfileIo.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/backendRestart.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/campaignClusterOpen.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/caseStudyFeed.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/chartTheme.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/correlationPresentation.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/correlationPresentation.test.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/cveAge.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/cveFilters.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/dataGridStandardGate.test.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/dateTimePickerSimpleGate.test.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/dateTimePickerStandardGate.test.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/detectLabels.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/detectLabels.test.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/displayPrefs.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/displayPrefsCore.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/displayText.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/domainTermTips.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/domainTermTips.test.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/domainValidation.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/drawerDatetimeFixes.test.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/drawerForgeMitreLinksGate.test.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/epssSparkline.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/epssSparkline.test.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/exploitationDisplay.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/exploitationDisplay.test.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/exportCommon.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/exportCsv.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/exportXlsx.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/extractIndicatorsFromCve.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/feedEpssUiCleanupGate.test.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/feedHealthStatus.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/forgeDeadControlsGate.test.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/forgeMitreNavigatorGate.test.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/forgeUrlTabClearGate.test.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/heatmapGrid.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/huntPackPdf.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/hybridFeedSearch.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/hybridFeedSearch.test.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/iconOnlyAriaGate.test.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/intelProvenance.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/investigationActors.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/investigationLabels.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/investigationLabels.test.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/investigationPdf.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/iocLookupMessages.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/iocLookupMessages.test.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/kevDeadline.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/kevDeadline.test.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/keyboardScope.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/keyboardScope.test.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/lazyWithReload.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/mitreNavigatorHelpers.test.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/momentumCache.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/morningBriefFormat.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/morningBriefFormat.test.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/motion.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/motion.test.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/nativeRangeGate.test.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/nativeSelectGate.test.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/notificationChime.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/notificationsApi.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/observableExtraction.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/openCveDrawer.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/patchReferences.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/patchReferences.test.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/patchRemediation.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/patchRemediation.test.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/pdfAiSummary.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/pdfReport.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/rechartsTheme.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/rechartsVersionGate.test.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/referenceRows.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/referenceRows.test.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/report.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/safeExternalUrl.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/safeExternalUrl.test.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/sectionLabels.test.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/securityArchitecturePdf.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/securityPostureGate.test.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/selectionAccentGate.test.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/severitySemantics.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/sharedObservables.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/sharedObservables.test.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/shellUrlState.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/shellUrlState.test.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/stackLocalSync.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/stackLocalSync.test.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/timezone.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/tutorial.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/typographyPrefs.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/userPreferences.js` | `gap` | — | ; No study-guide ownership found |
| `frontend/src/utils/userStack.js` | `gap` | — | ; No study-guide ownership found |
| `deploy/briefr-backend.service` | `covered` | `arch-monolith`, `devops-deploy` | exact path mention in chapter body/chips |
| `deploy/briefr-backup.service` | `gap` | — | ; No study-guide ownership found |
| `deploy/briefr-backup.sh` | `gap` | — | ; No study-guide ownership found |
| `deploy/briefr-backup.timer` | `gap` | — | ; No study-guide ownership found |
| `deploy/briefr-doctor.sh` | `gap` | — | ; No study-guide ownership found |
| `deploy/briefr-pg-backup.service` | `gap` | — | ; No study-guide ownership found |
| `deploy/briefr-pg-backup.sh` | `gap` | — | ; No study-guide ownership found |
| `deploy/briefr-pg-backup.timer` | `gap` | — | ; No study-guide ownership found |
| `deploy/briefr-restore.sh` | `gap` | — | ; No study-guide ownership found |
| `deploy/briefr-update.sh` | `gap` | — | ; No study-guide ownership found |
| `deploy/briefr.target` | `gap` | — | ; No study-guide ownership found |
| `deploy/check-backend.sh` | `gap` | — | ; No study-guide ownership found |
| `deploy/docker-compose.postgres.yml` | `gap` | — | ; No study-guide ownership found |
| `deploy/external-postgres.env.example` | `gap` | — | ; No study-guide ownership found |
| `deploy/lib.sh` | `gap` | — | ; No study-guide ownership found |
| `deploy/logrotate-briefr.conf` | `gap` | — | ; No study-guide ownership found |
| `deploy/nginx-briefr-http.conf` | `gap` | — | ; No study-guide ownership found |
| `deploy/nginx-briefr.conf` | `covered` | `devops-deploy` | exact path mention in chapter body/chips |
| `deploy/nginx-snippet-gzip.conf` | `gap` | — | ; No study-guide ownership found |
| `deploy/nginx-snippet-security-headers-https.conf` | `gap` | — | ; No study-guide ownership found |
| `deploy/nginx-snippet-security-headers.conf` | `gap` | — | ; No study-guide ownership found |
| `deploy/setup.sh` | `covered` | `devops-deploy` | exact path mention in chapter body/chips |
| `deploy/smoke-intel.sh` | `gap` | — | ; No study-guide ownership found |
| `backend/db/dialect.py` | `orphan_mention` | `be-data`, `roadmap-reversed` | named in STUDY_GUIDE.html; Path does not exist on disk — likely stale |
| `backend/tests/test_router_split.py` | `covered` | `be-bootstrap` | mentioned; outside primary inventory roots; Exists on disk but not under backend/frontend/src/deploy inventory roots |
| `scripts/export_intel_snapshot.py` | `covered` | `be-data` | mentioned; outside primary inventory roots; Exists on disk but not under backend/frontend/src/deploy inventory roots |
| `scripts/generate_security_corpus.py` | `covered` | `api-secarch` | mentioned; outside primary inventory roots; Exists on disk but not under backend/frontend/src/deploy inventory roots |
| `backend/tests/**` | `out_of_scope` | — | ; Aggregate into Testing strategy chapter; not file-mapped |
