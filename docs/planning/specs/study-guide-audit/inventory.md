# Study guide file inventory

_Regenerated 2026-07-22 by `scripts/audit_study_guide.py`. Do not hand-edit; re-run the script._

| Status | Count |
|--------|------:|
| `covered` | 647 |
| `weak` | 0 |
| `gap` | 0 |
| `orphan_mention` | 1 |
| `out_of_scope` | 86 |

| Path | Status | Chapters | Evidence / notes |
|------|--------|----------|------------------|
| `backend/ai/__init__.py` | `covered` | `api-ops`, `api-webhooks`, `ie-ml-providers`, `ie-scoring`, `in-jobs` | exact path mention in chapter body/chips |
| `backend/ai/gemini_client.py` | `covered` | `ie-ml-providers` | exact path mention in chapter body/chips |
| `backend/ai/groq_config.py` | `covered` | `ie-ml-providers` | exact path mention in chapter body/chips |
| `backend/ai/llm_pacing.py` | `covered` | `ie-ml-providers` | exact path mention in chapter body/chips |
| `backend/ai/llm_payload.py` | `covered` | `ie-ml-providers` | exact path mention in chapter body/chips |
| `backend/ai/llm_router.py` | `covered` | `arch-ai-restraint`, `ie-ml`, `ie-ml-providers` | exact path mention in chapter body/chips |
| `backend/ai/llm_session.py` | `covered` | `ie-ml-providers` | exact path mention in chapter body/chips |
| `backend/ai/model_catalog.py` | `covered` | `ie-ml-providers` | exact path mention in chapter body/chips |
| `backend/ai/openai_chat.py` | `covered` | `ie-ml-providers` | exact path mention in chapter body/chips |
| `backend/ai/operations_admin.py` | `covered` | `ie-ml-providers` | exact path mention in chapter body/chips |
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
| `backend/alembic.ini` | `covered` | `devops-deploy` | exact path mention in chapter body/chips |
| `backend/api_metering.py` | `covered` | `in-queue` | exact path mention in chapter body/chips |
| `backend/api_queue.py` | `covered` | `in-queue` | exact path mention in chapter body/chips |
| `backend/api_queue_operations.py` | `covered` | `in-queue` | exact path mention in chapter body/chips |
| `backend/auth/__init__.py` | `out_of_scope` | — | ; Empty/docstring-only package __init__.py marker |
| `backend/auth/passwords.py` | `covered` | `be-auth` | exact path mention in chapter body/chips |
| `backend/auth/repo.py` | `covered` | `be-auth` | exact path mention in chapter body/chips |
| `backend/auth/tokens.py` | `covered` | `be-auth` | exact path mention in chapter body/chips |
| `backend/auth/usernames.py` | `covered` | `be-auth` | exact path mention in chapter body/chips |
| `backend/auth_middleware.py` | `covered` | `be-auth` | exact path mention in chapter body/chips |
| `backend/backup/__init__.py` | `covered` | `api-ops` | exact path mention in chapter body/chips |
| `backend/backup/__main__.py` | `covered` | `api-ops` | exact path mention in chapter body/chips |
| `backend/backup/manager.py` | `covered` | `api-ops` | exact path mention in chapter body/chips |
| `backend/backup/postgres_util.py` | `covered` | `api-ops` | exact path mention in chapter body/chips |
| `backend/brief/__init__.py` | `out_of_scope` | — | ; Empty/docstring-only package __init__.py marker |
| `backend/brief/service.py` | `covered` | `api-ops`, `ie-brief` | exact path mention in chapter body/chips |
| `backend/catchup_mode.py` | `covered` | `in-scheduler` | exact path mention in chapter body/chips |
| `backend/config_schema.py` | `covered` | `be-config` | exact path mention in chapter body/chips |
| `backend/correlation/__init__.py` | `covered` | `ie-correlation` | exact path mention in chapter body/chips |
| `backend/correlation/attribution.py` | `covered` | `ie-correlation` | exact path mention in chapter body/chips |
| `backend/correlation/campaigns.py` | `covered` | `be-data`, `ie-correlation` | exact path mention in chapter body/chips |
| `backend/correlation/clusters.py` | `covered` | `ie-correlation` | exact path mention in chapter body/chips |
| `backend/correlation/confidence.py` | `covered` | `ie-correlation` | exact path mention in chapter body/chips |
| `backend/correlation/config.py` | `covered` | `be-data`, `ie-correlation` | exact path mention in chapter body/chips |
| `backend/correlation/confirm.py` | `covered` | `ie-correlation` | exact path mention in chapter body/chips |
| `backend/correlation/engine.py` | `covered` | `api-webhooks`, `ie-correlation`, `system-design` | exact path mention in chapter body/chips |
| `backend/correlation/feedback.py` | `covered` | `ie-correlation` | exact path mention in chapter body/chips |
| `backend/correlation/freshness.py` | `covered` | `ie-correlation` | exact path mention in chapter body/chips |
| `backend/correlation/hub_suppress.py` | `covered` | `ie-correlation` | exact path mention in chapter body/chips |
| `backend/correlation/ioc_graph.py` | `covered` | `ie-correlation` | exact path mention in chapter body/chips |
| `backend/correlation/ioc_normalize.py` | `covered` | `ie-correlation` | exact path mention in chapter body/chips |
| `backend/correlation/lifecycle.py` | `covered` | `ie-correlation` | exact path mention in chapter body/chips |
| `backend/correlation/local.py` | `covered` | `ie-correlation` | exact path mention in chapter body/chips |
| `backend/correlation/metrics.py` | `covered` | `be-data`, `ie-correlation` | exact path mention in chapter body/chips |
| `backend/correlation/narrative.py` | `covered` | `ie-correlation` | exact path mention in chapter body/chips |
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
| `backend/db/txn_boundaries.py` | `covered` | `be-data`, `system-design` | exact path mention in chapter body/chips |
| `backend/db/types.py` | `covered` | `be-data`, `system-design` | exact path mention in chapter body/chips |
| `backend/db/user_notifications.py` | `covered` | `be-data`, `system-design` | exact path mention in chapter body/chips |
| `backend/db/watchlist.py` | `covered` | `be-data`, `system-design` | exact path mention in chapter body/chips |
| `backend/db/webhooks.py` | `covered` | `be-data`, `system-design` | exact path mention in chapter body/chips |
| `backend/dependencies.py` | `covered` | `be-bootstrap` | exact path mention in chapter body/chips |
| `backend/destructive_actions.py` | `covered` | `api-scripts` | exact path mention in chapter body/chips |
| `backend/detection/__init__.py` | `covered` | `ie-detection` | exact path mention in chapter body/chips |
| `backend/detection/artifact_extract.py` | `covered` | `ie-detection` | exact path mention in chapter body/chips |
| `backend/detection/backlog.py` | `covered` | `ie-detection` | exact path mention in chapter body/chips |
| `backend/detection/class_queries.py` | `covered` | `ie-detection` | exact path mention in chapter body/chips |
| `backend/detection/class_router.py` | `covered` | `ie-detection` | exact path mention in chapter body/chips |
| `backend/detection/composer.py` | `covered` | `ie-detection` | exact path mention in chapter body/chips |
| `backend/detection/context.py` | `covered` | `ie-detection`, `in-jobs` | exact path mention in chapter body/chips |
| `backend/detection/context_llm_sync.py` | `covered` | `ie-detection` | exact path mention in chapter body/chips |
| `backend/detection/context_nuclei_sync.py` | `covered` | `ie-detection` | exact path mention in chapter body/chips |
| `backend/detection/context_sync.py` | `covered` | `ie-detection` | exact path mention in chapter body/chips |
| `backend/detection/nuclei_parser.py` | `covered` | `ie-detection` | exact path mention in chapter body/chips |
| `backend/detection/rule_sources.py` | `covered` | `ie-detection` | exact path mention in chapter body/chips |
| `backend/detection/siem_queries.py` | `covered` | `ie-detection` | exact path mention in chapter body/chips |
| `backend/detection/sigma_generator.py` | `covered` | `ie-detection` | exact path mention in chapter body/chips |
| `backend/detection/yara_generator.py` | `covered` | `ie-detection` | exact path mention in chapter body/chips |
| `backend/diagnostics/__init__.py` | `out_of_scope` | — | ; Empty/docstring-only package __init__.py marker |
| `backend/diagnostics/support_pack.py` | `covered` | `api-ops` | exact path mention in chapter body/chips |
| `backend/enrichment/__init__.py` | `covered` | `ie-ml` | exact path mention in chapter body/chips |
| `backend/enrichment/cve.py` | `covered` | `api-proof`, `ie-ml` | exact path mention in chapter body/chips |
| `backend/enrichment/domain_validation.py` | `covered` | `api-proof`, `ie-ml` | exact path mention in chapter body/chips |
| `backend/enrichment/ioc.py` | `covered` | `api-proof`, `ie-ml` | exact path mention in chapter body/chips |
| `backend/feeds/__init__.py` | `covered` | `in-feeds` | exact path mention in chapter body/chips |
| `backend/feeds/ai_context.py` | `covered` | `in-feeds` | exact path mention in chapter body/chips |
| `backend/feeds/atlas.py` | `covered` | `in-feeds` | exact path mention in chapter body/chips |
| `backend/feeds/case_study_feed.py` | `covered` | `in-feeds` | exact path mention in chapter body/chips |
| `backend/feeds/cpe_catalog.py` | `covered` | `in-feeds` | exact path mention in chapter body/chips |
| `backend/feeds/cve_record_v5.py` | `covered` | `in-feeds` | exact path mention in chapter body/chips |
| `backend/feeds/cvelistv5.py` | `covered` | `in-feeds` | exact path mention in chapter body/chips |
| `backend/feeds/epss.py` | `covered` | `in-feeds` | exact path mention in chapter body/chips |
| `backend/feeds/errors.py` | `covered` | `in-feeds` | exact path mention in chapter body/chips |
| `backend/feeds/exploit_common.py` | `covered` | `in-feeds` | exact path mention in chapter body/chips |
| `backend/feeds/exploit_sync.py` | `covered` | `in-feeds` | exact path mention in chapter body/chips |
| `backend/feeds/exploitdb.py` | `covered` | `in-feeds` | exact path mention in chapter body/chips |
| `backend/feeds/extended.py` | `covered` | `in-feeds` | exact path mention in chapter body/chips |
| `backend/feeds/file_identity.py` | `covered` | `in-feeds` | exact path mention in chapter body/chips |
| `backend/feeds/github_helpers.py` | `covered` | `in-feeds` | exact path mention in chapter body/chips |
| `backend/feeds/incident_news.py` | `covered` | `in-feeds` | exact path mention in chapter body/chips |
| `backend/feeds/incident_sources.py` | `covered` | `in-feeds` | exact path mention in chapter body/chips |
| `backend/feeds/kev.py` | `covered` | `in-feeds` | exact path mention in chapter body/chips |
| `backend/feeds/metasploit_modules.py` | `covered` | `in-feeds` | exact path mention in chapter body/chips |
| `backend/feeds/mitre.py` | `covered` | `in-feeds` | exact path mention in chapter body/chips |
| `backend/feeds/nuclei_index.py` | `covered` | `in-feeds` | exact path mention in chapter body/chips |
| `backend/feeds/nvd.py` | `covered` | `in-feeds` | exact path mention in chapter body/chips |
| `backend/feeds/osv.py` | `covered` | `in-feeds` | exact path mention in chapter body/chips |
| `backend/feeds/otx.py` | `covered` | `in-feeds` | exact path mention in chapter body/chips |
| `backend/feeds/otx_continuous.py` | `covered` | `in-feeds` | exact path mention in chapter body/chips |
| `backend/feeds/poc_github.py` | `covered` | `in-feeds` | exact path mention in chapter body/chips |
| `backend/feeds/threatfox.py` | `covered` | `in-feeds` | exact path mention in chapter body/chips |
| `backend/feeds/vulncheck_kev.py` | `covered` | `in-feeds` | exact path mention in chapter body/chips |
| `backend/feeds/vulnrichment.py` | `covered` | `in-feeds` | exact path mention in chapter body/chips |
| `backend/intel/__init__.py` | `out_of_scope` | — | ; Empty/docstring-only package __init__.py marker |
| `backend/intel/provenance.py` | `covered` | `ie-threatmodel` | exact path mention in chapter body/chips |
| `backend/ioc/__init__.py` | `out_of_scope` | — | ; Empty/docstring-only package __init__.py marker |
| `backend/ioc/retro_match.py` | `covered` | `ie-threatmodel` | exact path mention in chapter body/chips |
| `backend/jobs/__init__.py` | `covered` | `in-jobs` | exact path mention in chapter body/chips |
| `backend/jobs/app.py` | `covered` | `in-jobs` | exact path mention in chapter body/chips |
| `backend/jobs/context.py` | `covered` | `in-jobs` | exact path mention in chapter body/chips |
| `backend/jobs/retry_policy.py` | `covered` | `in-jobs` | exact path mention in chapter body/chips |
| `backend/jobs/tasks.py` | `covered` | `in-jobs` | exact path mention in chapter body/chips |
| `backend/jobs/worker.py` | `covered` | `in-jobs` | exact path mention in chapter body/chips |
| `backend/main.py` | `covered` | `be-bootstrap` | exact path mention in chapter body/chips |
| `backend/matching/__init__.py` | `out_of_scope` | — | ; Empty/docstring-only package __init__.py marker |
| `backend/matching/cpe.py` | `covered` | `ie-matching` | exact path mention in chapter body/chips |
| `backend/metrics/__init__.py` | `out_of_scope` | — | ; Empty/docstring-only package __init__.py marker |
| `backend/metrics/request_counter.py` | `covered` | `api-ops`, `api-scripts` | exact path mention in chapter body/chips |
| `backend/migration/__init__.py` | `out_of_scope` | — | ; Empty/docstring-only package __init__.py marker |
| `backend/migration/sqlite_to_postgres.py` | `covered` | `api-ops` | exact path mention in chapter body/chips |
| `backend/ml/__init__.py` | `out_of_scope` | — | ; Empty/docstring-only package __init__.py marker |
| `backend/ml/embeddings.py` | `covered` | `arch-ai-restraint`, `arch-resources`, `ie-ml`, `ie-retrieval-ops` | exact path mention in chapter body/chips |
| `backend/ml/product_extraction.py` | `covered` | `ie-ml` | exact path mention in chapter body/chips |
| `backend/monitoring/__init__.py` | `out_of_scope` | — | ; Empty/docstring-only package __init__.py marker |
| `backend/monitoring/api_key_health.py` | `covered` | `api-ops` | exact path mention in chapter body/chips |
| `backend/monitoring/notifications.py` | `covered` | `api-ops` | exact path mention in chapter body/chips |
| `backend/notifications/emit.py` | `covered` | `api-usersettings` | exact path mention in chapter body/chips |
| `backend/onboarding/__init__.py` | `out_of_scope` | — | ; Empty/docstring-only package __init__.py marker |
| `backend/onboarding/checklist.py` | `covered` | `api-usersettings` | exact path mention in chapter body/chips |
| `backend/operator_settings.py` | `covered` | `be-config` | exact path mention in chapter body/chips |
| `backend/preferences/display_validate.py` | `covered` | `api-usersettings` | exact path mention in chapter body/chips |
| `backend/preferences/repo.py` | `covered` | `api-usersettings` | exact path mention in chapter body/chips |
| `backend/preferences/validate.py` | `covered` | `api-usersettings` | exact path mention in chapter body/chips |
| `backend/proof/__init__.py` | `out_of_scope` | — | ; Empty/docstring-only package __init__.py marker |
| `backend/proof/bench.py` | `covered` | `api-proof` | exact path mention in chapter body/chips |
| `backend/pyproject.toml` | `covered` | `be-bootstrap` | exact path mention in chapter body/chips |
| `backend/pytest.ini` | `covered` | `devops-deploy` | exact path mention in chapter body/chips |
| `backend/rate_limit.py` | `covered` | `arch-resources`, `be-ratelimit` | exact path mention in chapter body/chips |
| `backend/rate_limit_store.py` | `covered` | `be-ratelimit` | exact path mention in chapter body/chips |
| `backend/read_cache.py` | `covered` | `api-ops` | exact path mention in chapter body/chips |
| `backend/redact.py` | `covered` | `be-logging` | exact path mention in chapter body/chips |
| `backend/resilient_client.py` | `covered` | `in-queue` | exact path mention in chapter body/chips |
| `backend/resource_collector.py` | `covered` | `api-ops` | exact path mention in chapter body/chips |
| `backend/routers/__init__.py` | `covered` | `api-routers` | exact path mention in chapter body/chips |
| `backend/routers/_validators.py` | `covered` | `api-routers` | exact path mention in chapter body/chips |
| `backend/routers/admin/__init__.py` | `covered` | `api-routers` | exact path mention in chapter body/chips |
| `backend/routers/admin/ai_ops.py` | `covered` | `api-routers`, `ie-retrieval-ops` | exact path mention in chapter body/chips |
| `backend/routers/admin/catchup.py` | `covered` | `api-routers`, `in-scheduler` | exact path mention in chapter body/chips |
| `backend/routers/admin/config.py` | `covered` | `api-routers` | exact path mention in chapter body/chips |
| `backend/routers/admin/data_ops.py` | `covered` | `api-routers` | exact path mention in chapter body/chips |
| `backend/routers/admin/database.py` | `covered` | `api-routers` | exact path mention in chapter body/chips |
| `backend/routers/admin/diagnostics.py` | `covered` | `api-routers` | exact path mention in chapter body/chips |
| `backend/routers/admin/feeds.py` | `covered` | `api-routers` | exact path mention in chapter body/chips |
| `backend/routers/admin/helpers.py` | `covered` | `api-routers` | exact path mention in chapter body/chips |
| `backend/routers/admin/jobs.py` | `covered` | `api-routers`, `in-jobs`, `in-scheduler` | exact path mention in chapter body/chips |
| `backend/routers/admin/router.py` | `covered` | `api-routers` | exact path mention in chapter body/chips |
| `backend/routers/admin/storage.py` | `covered` | `api-routers` | exact path mention in chapter body/chips |
| `backend/routers/admin/system.py` | `covered` | `api-routers` | exact path mention in chapter body/chips |
| `backend/routers/admin/tokens.py` | `covered` | `api-routers` | exact path mention in chapter body/chips |
| `backend/routers/admin/webhooks.py` | `covered` | `api-routers` | exact path mention in chapter body/chips |
| `backend/routers/admin/webhooks_logs.py` | `covered` | `api-routers` | exact path mention in chapter body/chips |
| `backend/routers/atlas.py` | `covered` | `api-routers` | exact path mention in chapter body/chips |
| `backend/routers/auth.py` | `covered` | `api-routers` | exact path mention in chapter body/chips |
| `backend/routers/brief.py` | `covered` | `api-routers` | exact path mention in chapter body/chips |
| `backend/routers/config.py` | `covered` | `api-routers` | exact path mention in chapter body/chips |
| `backend/routers/correlation.py` | `covered` | `api-routers` | exact path mention in chapter body/chips |
| `backend/routers/cves/__init__.py` | `covered` | `api-routers` | exact path mention in chapter body/chips |
| `backend/routers/cves/changes.py` | `covered` | `api-routers` | exact path mention in chapter body/chips |
| `backend/routers/cves/common.py` | `covered` | `api-routers` | exact path mention in chapter body/chips |
| `backend/routers/cves/detail.py` | `covered` | `api-routers` | exact path mention in chapter body/chips |
| `backend/routers/cves/intel.py` | `covered` | `api-routers`, `arch-connectivity` | exact path mention in chapter body/chips |
| `backend/routers/cves/list.py` | `covered` | `api-routers`, `api-secarch` | exact path mention in chapter body/chips |
| `backend/routers/cves/models.py` | `covered` | `api-routers` | exact path mention in chapter body/chips |
| `backend/routers/detection_backlog.py` | `covered` | `api-routers` | exact path mention in chapter body/chips |
| `backend/routers/forge.py` | `covered` | `api-routers`, `api-secarch` | exact path mention in chapter body/chips |
| `backend/routers/health.py` | `covered` | `api-routers` | exact path mention in chapter body/chips |
| `backend/routers/ioc.py` | `covered` | `api-routers` | exact path mention in chapter body/chips |
| `backend/routers/me.py` | `covered` | `api-routers`, `fe-state` | exact path mention in chapter body/chips |
| `backend/routers/meta.py` | `covered` | `api-routers` | exact path mention in chapter body/chips |
| `backend/routers/notifications_me.py` | `covered` | `api-routers` | exact path mention in chapter body/chips |
| `backend/routers/proof.py` | `covered` | `api-routers` | exact path mention in chapter body/chips |
| `backend/routers/refresh.py` | `covered` | `api-routers` | exact path mention in chapter body/chips |
| `backend/routers/search.py` | `covered` | `api-routers` | exact path mention in chapter body/chips |
| `backend/routers/stack_catalog.py` | `covered` | `api-routers` | exact path mention in chapter body/chips |
| `backend/routers/threat_model.py` | `covered` | `api-routers` | exact path mention in chapter body/chips |
| `backend/routers/wallboard.py` | `covered` | `api-routers` | exact path mention in chapter body/chips |
| `backend/routers/watchlist.py` | `covered` | `api-routers` | exact path mention in chapter body/chips |
| `backend/scheduler.py` | `covered` | `in-scheduler` | exact path mention in chapter body/chips |
| `backend/scheduler_locks.py` | `covered` | `in-scheduler` | exact path mention in chapter body/chips |
| `backend/scoring/__init__.py` | `covered` | `ie-scoring` | exact path mention in chapter body/chips |
| `backend/scoring/asset_match.py` | `covered` | `ie-matching` | exact path mention in chapter body/chips |
| `backend/scoring/environment.py` | `covered` | `ie-scoring` | exact path mention in chapter body/chips |
| `backend/scoring/priority.py` | `covered` | `ie-scoring` | exact path mention in chapter body/chips |
| `backend/scoring/risk.py` | `covered` | `api-routers`, `arch-ai-restraint`, `ie-correlation`, `ie-scoring` | exact path mention in chapter body/chips |
| `backend/scoring/ssvc.py` | `covered` | `ie-scoring` | exact path mention in chapter body/chips |
| `backend/scoring/threat.py` | `covered` | `ie-scoring` | exact path mention in chapter body/chips |
| `backend/scripts/backfill_poc.py` | `covered` | `api-scripts` | exact path mention in chapter body/chips |
| `backend/scripts/create_user.py` | `covered` | `api-scripts` | exact path mention in chapter body/chips |
| `backend/scripts/delete_user.py` | `covered` | `api-scripts` | exact path mention in chapter body/chips |
| `backend/scripts/sync_env.py` | `covered` | `api-scripts` | exact path mention in chapter body/chips |
| `backend/security_architecture/__init__.py` | `covered` | `api-secarch` | exact path mention in chapter body/chips |
| `backend/security_architecture/corpus/abuse_cases.yaml` | `covered` | `api-secarch` | exact path mention in chapter body/chips |
| `backend/security_architecture/corpus/api_inventory.yaml` | `covered` | `api-secarch` | exact path mention in chapter body/chips |
| `backend/security_architecture/corpus/components.yaml` | `covered` | `api-secarch` | exact path mention in chapter body/chips |
| `backend/security_architecture/corpus/controls.yaml` | `covered` | `api-secarch` | exact path mention in chapter body/chips |
| `backend/security_architecture/corpus/db_tables.yaml` | `covered` | `api-secarch` | exact path mention in chapter body/chips |
| `backend/security_architecture/corpus/graphs/architecture.json` | `covered` | `api-secarch` | exact path mention in chapter body/chips |
| `backend/security_architecture/corpus/manifest.yaml` | `covered` | `api-secarch` | exact path mention in chapter body/chips |
| `backend/security_architecture/corpus/reviews.yaml` | `covered` | `api-secarch` | exact path mention in chapter body/chips |
| `backend/security_architecture/corpus/risks.yaml` | `covered` | `api-secarch` | exact path mention in chapter body/chips |
| `backend/security_architecture/corpus/scheduler_jobs.yaml` | `covered` | `api-secarch` | exact path mention in chapter body/chips |
| `backend/security_architecture/corpus/security_decisions.yaml` | `covered` | `api-secarch` | exact path mention in chapter body/chips |
| `backend/security_architecture/corpus/self_stack.yaml` | `covered` | `api-secarch` | exact path mention in chapter body/chips |
| `backend/security_architecture/corpus/threat_scenarios.yaml` | `covered` | `api-secarch` | exact path mention in chapter body/chips |
| `backend/security_architecture/corpus/trust_boundaries.yaml` | `covered` | `api-secarch` | exact path mention in chapter body/chips |
| `backend/security_architecture/corpus_drift.py` | `covered` | `api-secarch` | exact path mention in chapter body/chips |
| `backend/security_architecture/corpus_loader.py` | `covered` | `api-secarch` | exact path mention in chapter body/chips |
| `backend/security_architecture/frameworks/__init__.py` | `covered` | `api-secarch` | exact path mention in chapter body/chips |
| `backend/security_architecture/frameworks/aggregate.py` | `covered` | `api-secarch` | exact path mention in chapter body/chips |
| `backend/security_architecture/frameworks/reference.py` | `covered` | `api-secarch` | exact path mention in chapter body/chips |
| `backend/security_architecture/frameworks/scope.py` | `covered` | `api-secarch` | exact path mention in chapter body/chips |
| `backend/security_architecture/graphs.py` | `covered` | `api-secarch` | exact path mention in chapter body/chips |
| `backend/security_architecture/merge.py` | `covered` | `api-secarch` | exact path mention in chapter body/chips |
| `backend/security_architecture/routers/__init__.py` | `out_of_scope` | — | ; Empty/docstring-only package __init__.py marker |
| `backend/security_architecture/routers/security_architecture.py` | `covered` | `api-secarch` | exact path mention in chapter body/chips |
| `backend/services/__init__.py` | `out_of_scope` | — | ; Empty/docstring-only package __init__.py marker |
| `backend/services/retrieval_health.py` | `covered` | `ie-retrieval-ops` | exact path mention in chapter body/chips |
| `backend/services/semantic_search.py` | `covered` | `api-proof` | exact path mention in chapter body/chips |
| `backend/services/stack_backfill_worker.py` | `covered` | `api-proof`, `in-jobs` | exact path mention in chapter body/chips |
| `backend/settings.py` | `covered` | `be-config` | exact path mention in chapter body/chips |
| `backend/settings_crypto.py` | `covered` | `be-config` | exact path mention in chapter body/chips |
| `backend/source_rate_limits.py` | `covered` | `in-queue` | exact path mention in chapter body/chips |
| `backend/storage_metrics.py` | `covered` | `api-ops` | exact path mention in chapter body/chips |
| `backend/structured_logging.py` | `covered` | `be-logging` | exact path mention in chapter body/chips |
| `backend/task_registry.py` | `covered` | `api-scripts` | exact path mention in chapter body/chips |
| `backend/templates/__init__.py` | `out_of_scope` | — | ; Empty/docstring-only package __init__.py marker |
| `backend/templates/intelligence.py` | `covered` | `api-proof` | exact path mention in chapter body/chips |
| `backend/threat_model/__init__.py` | `out_of_scope` | — | ; Empty/docstring-only package __init__.py marker |
| `backend/threat_model/scenarios.py` | `covered` | `ie-threatmodel` | exact path mention in chapter body/chips |
| `backend/tracking.py` | `covered` | `api-scripts` | exact path mention in chapter body/chips |
| `backend/wallboard/__init__.py` | `out_of_scope` | — | ; Empty/docstring-only package __init__.py marker |
| `backend/wallboard/service.py` | `covered` | `api-ops` | exact path mention in chapter body/chips |
| `backend/wallboard/session.py` | `covered` | `api-ops` | exact path mention in chapter body/chips |
| `backend/webhooks/__init__.py` | `covered` | `api-webhooks` | exact path mention in chapter body/chips |
| `backend/webhooks/alerts.py` | `covered` | `api-webhooks` | exact path mention in chapter body/chips |
| `backend/webhooks/destinations.py` | `covered` | `api-webhooks` | exact path mention in chapter body/chips |
| `backend/webhooks/engine.py` | `covered` | `api-webhooks` | exact path mention in chapter body/chips |
| `backend/webhooks/sender.py` | `covered` | `api-webhooks` | exact path mention in chapter body/chips |
| `backend/webhooks/ssrf.py` | `covered` | `api-webhooks` | exact path mention in chapter body/chips |
| `frontend/src/App.css` | `covered` | `fe-design` | exact path mention in chapter body/chips |
| `frontend/src/App.jsx` | `covered` | `fe-analyst-shell` | exact path mention in chapter body/chips |
| `frontend/src/api.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/api.outboundJobs.test.js` | `out_of_scope` | — | ; FE gate/unit test; aggregate into Testing strategy chapter |
| `frontend/src/apiOutboundJobs.js` | `covered` | `in-jobs` | exact path mention in chapter body/chips |
| `frontend/src/components/AboutModal.css` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/AboutModal.jsx` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/ApiQueueIndicator.css` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/ApiQueueIndicator.jsx` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/AppErrorBoundary.jsx` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/AssetProfileManage.jsx` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/AssetRememberToggle.jsx` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/AssetWarning.css` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/AssetWarning.jsx` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/AssetWizard.css` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/AssetWizard.jsx` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/BriefCharts.css` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/BriefCharts.jsx` | `covered` | `fe-forge-wallboard`, `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/CVECard.css` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/CVECard.jsx` | `covered` | `fe-analyst-shell`, `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/CVEFeed.css` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/CVEFeed.jsx` | `covered` | `fe-analyst-shell`, `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/CaseStudies.css` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/CaseStudies.jsx` | `covered` | `fe-forge-wallboard`, `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/CommandPalette.css` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/CommandPalette.jsx` | `covered` | `fe-analyst-shell`, `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/ControlTooltip.css` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/ControlTooltip.jsx` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/CveDescriptionClamp.css` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/CveDescriptionClamp.jsx` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/DetailDrawer/CorrelationSuppressModal.css` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/DetailDrawer/CorrelationSuppressModal.jsx` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/DetailDrawer/DetectTab.jsx` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/DetailDrawer/IntelProvenanceLine.jsx` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/DetailDrawer/IntelTab.jsx` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/DetailDrawer/OverviewTab.jsx` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/DetailDrawer/RelatedTab.jsx` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/DetailDrawer/helpers.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/DetailDrawer/index.jsx` | `covered` | `fe-analyst-shell`, `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/DetailDrawer.css` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/DigestModal.css` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/DigestModal.jsx` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/DrawerAtlasSection.jsx` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/ExplainTip.css` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/ExplainTip.jsx` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/FeedVisibleRange.jsx` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/FilterBar.css` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/FilterBar.jsx` | `covered` | `fe-analyst-shell`, `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/Forge.css` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/Forge.jsx` | `covered` | `fe-forge-wallboard`, `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/Header.css` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/Header.jsx` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/HeaderClock.jsx` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/Hero.css` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/Hero.jsx` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/IOCLookup.css` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/IOCLookup.jsx` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/InvestigationPanel.css` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/InvestigationPanel.jsx` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/MorningBrief.css` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/MorningBrief.jsx` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/NotificationBell.css` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/NotificationBell.jsx` | `covered` | `fe-analyst-shell`, `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/PdfExportModal.css` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/PdfExportModal.jsx` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/RequireAdmin.jsx` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/RequireAuth.jsx` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/ScrollToTop.css` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/ScrollToTop.jsx` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/SessionIdleWarning.css` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/SessionIdleWarning.jsx` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/SessionLockOverlay.css` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/SessionLockOverlay.jsx` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/SeverityLegend.css` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/SeverityLegend.jsx` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/ShortcutsPanel.css` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/ShortcutsPanel.jsx` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/Sidebar.css` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/Sidebar.jsx` | `covered` | `fe-admin-shell`, `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/StatsRow.css` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/StatsRow.jsx` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/TimeWindowPicker.css` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/TimeWindowPicker.jsx` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/TimelineHeatmap.css` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/TimelineHeatmap.jsx` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/Toast.jsx` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/ToolErrorBoundary.jsx` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/TutorialOverlay.css` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/TutorialOverlay.jsx` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/UserMenu.css` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/UserMenu.jsx` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/WhatChangedPanel.css` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/WhatChangedPanel.jsx` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/briefVendorChartRecharts.jsx` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/forge/BacklogView.jsx` | `covered` | `fe-forge-wallboard`, `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/forge/CampaignsView.jsx` | `covered` | `fe-forge-wallboard`, `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/forge/CoverageView.jsx` | `covered` | `fe-forge-wallboard`, `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/forge/HuntPackRail.jsx` | `covered` | `fe-forge-wallboard`, `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/forge/LibraryView.jsx` | `covered` | `fe-forge-wallboard`, `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/forge/ScenariosView.jsx` | `covered` | `fe-forge-wallboard`, `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/forge/mitreTacticOrder.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/forge/shared.jsx` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/ioc/IOCLookup.loc.test.js` | `out_of_scope` | — | ; FE gate/unit test; aggregate into Testing strategy chapter |
| `frontend/src/components/ioc/IOCQuotaPanel.jsx` | `covered` | `fe-state` | exact path mention in chapter body/chips |
| `frontend/src/components/ioc/IOCResultComponents.jsx` | `covered` | `fe-state` | exact path mention in chapter body/chips |
| `frontend/src/components/ioc/iocUtils.js` | `covered` | `fe-state` | exact path mention in chapter body/chips |
| `frontend/src/components/ioc/iocUtils.test.js` | `out_of_scope` | — | ; FE gate/unit test; aggregate into Testing strategy chapter |
| `frontend/src/components/timeWindowDateUtils.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/components/timeWindowDateUtils.test.js` | `out_of_scope` | — | ; FE gate/unit test; aggregate into Testing strategy chapter |
| `frontend/src/components/ui/AlertDialog.jsx` | `covered` | `fe-design` | exact path mention in chapter body/chips |
| `frontend/src/components/ui/AsyncState.jsx` | `covered` | `fe-design` | exact path mention in chapter body/chips |
| `frontend/src/components/ui/AsyncState.test.js` | `out_of_scope` | — | ; FE gate/unit test; aggregate into Testing strategy chapter |
| `frontend/src/components/ui/Badge.jsx` | `covered` | `fe-design` | exact path mention in chapter body/chips |
| `frontend/src/components/ui/Button.jsx` | `covered` | `fe-design` | exact path mention in chapter body/chips |
| `frontend/src/components/ui/Card.jsx` | `covered` | `fe-design` | exact path mention in chapter body/chips |
| `frontend/src/components/ui/ChartDataTable.jsx` | `covered` | `fe-design` | exact path mention in chapter body/chips |
| `frontend/src/components/ui/ChartShell.jsx` | `covered` | `fe-design` | exact path mention in chapter body/chips |
| `frontend/src/components/ui/Checkbox.jsx` | `covered` | `fe-design` | exact path mention in chapter body/chips |
| `frontend/src/components/ui/ConfirmModal.jsx` | `covered` | `fe-design` | exact path mention in chapter body/chips |
| `frontend/src/components/ui/DataGrid.css` | `covered` | `fe-design` | exact path mention in chapter body/chips |
| `frontend/src/components/ui/DataGrid.jsx` | `covered` | `fe-design` | exact path mention in chapter body/chips |
| `frontend/src/components/ui/DateTimePicker.css` | `covered` | `fe-design` | exact path mention in chapter body/chips |
| `frontend/src/components/ui/DateTimePicker.jsx` | `covered` | `fe-design` | exact path mention in chapter body/chips |
| `frontend/src/components/ui/DateTimeRangeField.css` | `covered` | `fe-design` | exact path mention in chapter body/chips |
| `frontend/src/components/ui/DateTimeRangeField.jsx` | `covered` | `fe-design` | exact path mention in chapter body/chips |
| `frontend/src/components/ui/DropdownMenu.jsx` | `covered` | `fe-design` | exact path mention in chapter body/chips |
| `frontend/src/components/ui/EmptyState.jsx` | `covered` | `fe-design` | exact path mention in chapter body/chips |
| `frontend/src/components/ui/ErrorState.jsx` | `covered` | `fe-design` | exact path mention in chapter body/chips |
| `frontend/src/components/ui/Modal.jsx` | `covered` | `fe-design` | exact path mention in chapter body/chips |
| `frontend/src/components/ui/Pill.jsx` | `covered` | `fe-design` | exact path mention in chapter body/chips |
| `frontend/src/components/ui/ReferenceTooltip.jsx` | `covered` | `fe-design` | exact path mention in chapter body/chips |
| `frontend/src/components/ui/Select.jsx` | `covered` | `fe-design` | exact path mention in chapter body/chips |
| `frontend/src/components/ui/Skeleton.jsx` | `covered` | `fe-design` | exact path mention in chapter body/chips |
| `frontend/src/components/ui/SkeletonStack.jsx` | `covered` | `fe-design` | exact path mention in chapter body/chips |
| `frontend/src/components/ui/Slider.jsx` | `covered` | `fe-design` | exact path mention in chapter body/chips |
| `frontend/src/components/ui/StatCard.jsx` | `covered` | `fe-design` | exact path mention in chapter body/chips |
| `frontend/src/components/ui/Switch.jsx` | `covered` | `fe-design` | exact path mention in chapter body/chips |
| `frontend/src/components/ui/Tabs.jsx` | `covered` | `fe-design` | exact path mention in chapter body/chips |
| `frontend/src/components/ui/Toast.jsx` | `covered` | `fe-design` | exact path mention in chapter body/chips |
| `frontend/src/components/ui/Tooltip.jsx` | `covered` | `fe-design` | exact path mention in chapter body/chips |
| `frontend/src/components/ui/Tooltip.test.js` | `out_of_scope` | — | ; FE gate/unit test; aggregate into Testing strategy chapter |
| `frontend/src/components/ui/index.js` | `covered` | `fe-design` | exact path mention in chapter body/chips |
| `frontend/src/components/ui/ui.css` | `covered` | `fe-design` | exact path mention in chapter body/chips |
| `frontend/src/config/assetCatalog.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/config/caseStudySources.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/context/AssetProfileContext.jsx` | `covered` | `fe-analyst-shell`, `fe-react`, `fe-state` | exact path mention in chapter body/chips |
| `frontend/src/context/AuthContext.jsx` | `covered` | `fe-analyst-shell`, `fe-react`, `fe-state` | exact path mention in chapter body/chips |
| `frontend/src/context/InvestigationContext.jsx` | `covered` | `fe-state` | exact path mention in chapter body/chips |
| `frontend/src/hooks/useAsync.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/hooks/useInactivityTimeout.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/hooks/useModalLayer.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/hooks/useVisibilityAwareInterval.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/hooks/useWatchlist.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/main.jsx` | `covered` | `fe-react` | exact path mention in chapter body/chips |
| `frontend/src/pages/AdminPage.css` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/LegalPage.css` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/LegalPage.jsx` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/LoginPage.css` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/LoginPage.jsx` | `covered` | `fe-admin-shell`, `fe-analyst-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/PrivacyPage.jsx` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/TermsPage.jsx` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/WallboardPage.css` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/WallboardPage.jsx` | `covered` | `fe-admin-shell`, `fe-forge-wallboard` | exact path mention in chapter body/chips |
| `frontend/src/pages/admin/AdminPage.jsx` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/admin/AiOperationsPage.jsx` | `covered` | `fe-admin-shell`, `ie-retrieval-ops` | exact path mention in chapter body/chips |
| `frontend/src/pages/admin/AlertsPage.jsx` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/admin/ApiKeyHealthPanel.jsx` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/admin/ApiKeysPage.jsx` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/admin/AuditLogPage.jsx` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/admin/BackupsPage.jsx` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/admin/CatchupCard.jsx` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/admin/ComingSoonPage.jsx` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/admin/DatabasePage.jsx` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/admin/DbExplorerPanel.jsx` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/admin/DisplayPage.jsx` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/admin/FeedHealthPage.jsx` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/admin/IngestLogPage.jsx` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/admin/OutboundJobsPanel.jsx` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/admin/OverviewPage.jsx` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/admin/RateLimitPage.jsx` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/admin/ResourcesPage.jsx` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/admin/SchedulerPage.jsx` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/admin/SearchTokensPanel.jsx` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/admin/SecurityPage.jsx` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/admin/SecurityPosturePage.css` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/admin/SecurityPosturePage.jsx` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/admin/SessionsPage.jsx` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/admin/Sidebar.jsx` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/admin/StatusBar.jsx` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/admin/StoragePage.jsx` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/admin/WatchlistPage.jsx` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/admin/WebhookDestinationCard.jsx` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/admin/WebhooksPage.css` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/admin/WebhooksPage.jsx` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/admin/adminFormFieldGate.test.js` | `out_of_scope` | — | ; FE gate/unit test; aggregate into Testing strategy chapter |
| `frontend/src/pages/admin/adminJobAck.js` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/admin/adminNav.test.js` | `out_of_scope` | — | ; FE gate/unit test; aggregate into Testing strategy chapter |
| `frontend/src/pages/admin/adminUrlPageClearGate.test.js` | `out_of_scope` | — | ; FE gate/unit test; aggregate into Testing strategy chapter |
| `frontend/src/pages/admin/catalog.js` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/admin/catchupCopy.js` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/admin/catchupCopy.test.js` | `out_of_scope` | — | ; FE gate/unit test; aggregate into Testing strategy chapter |
| `frontend/src/pages/admin/circuitLabels.js` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/admin/constants.js` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/admin/formatters.js` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/admin/formatters.test.js` | `out_of_scope` | — | ; FE gate/unit test; aggregate into Testing strategy chapter |
| `frontend/src/pages/admin/intelStatus.js` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/admin/jobActions.js` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/admin/jobActions.test.js` | `out_of_scope` | — | ; FE gate/unit test; aggregate into Testing strategy chapter |
| `frontend/src/pages/admin/jobStatus.js` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/admin/needsAttention.js` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/admin/needsAttention.test.js` | `out_of_scope` | — | ; FE gate/unit test; aggregate into Testing strategy chapter |
| `frontend/src/pages/admin/outboundJobsCopy.js` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/admin/outboundJobsCopy.test.js` | `out_of_scope` | — | ; FE gate/unit test; aggregate into Testing strategy chapter |
| `frontend/src/pages/admin/rateLimits.js` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/admin/resourceChartUtils.js` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/admin/resourceChartUtils.test.js` | `out_of_scope` | — | ; FE gate/unit test; aggregate into Testing strategy chapter |
| `frontend/src/pages/admin/resourcesChartsRecharts.jsx` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/admin/shared/AdminBreadcrumbs.jsx` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/admin/shared/AdminDataGrid.jsx` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/admin/shared/AdminSkeletons.jsx` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/admin/shared/AsyncSection.jsx` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/admin/shared/ConfirmModal.jsx` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/admin/shared/DangerZone.jsx` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/admin/shared/DiffReviewModal.jsx` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/admin/shared/ErrorBoundary.jsx` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/admin/shared/GuardedPurgePanel.jsx` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/admin/shared/HelpTip.jsx` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/admin/shared/JobErrorsPanel.jsx` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/admin/shared/JobTable.jsx` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/admin/shared/NeedsAttentionPanel.jsx` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/admin/shared/NotificationCenter.jsx` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/admin/shared/OperationTracker.jsx` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/admin/shared/OpsCharts.jsx` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/admin/shared/RestartBanner.jsx` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/admin/shared/StatCard.jsx` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/admin/shared/StatusLegend.jsx` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/admin/shared/ToggleSwitch.jsx` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/admin/shared/backupChartUtils.js` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/admin/shared/backupChartUtils.test.js` | `out_of_scope` | — | ; FE gate/unit test; aggregate into Testing strategy chapter |
| `frontend/src/pages/admin/shared/opsChartsRecharts.jsx` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/admin/toastCopy.js` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/admin/toastCopy.test.js` | `out_of_scope` | — | ; FE gate/unit test; aggregate into Testing strategy chapter |
| `frontend/src/pages/security-architecture/ContextRail.jsx` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/security-architecture/GlobalSearch.jsx` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/security-architecture/SecurityArchitecturePage.css` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/security-architecture/SecurityArchitecturePage.jsx` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/security-architecture/constants.js` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/security-architecture/sections/AbuseCasesSection.jsx` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/security-architecture/sections/ArchitectureGraphSection.jsx` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/security-architecture/sections/AttackSurfaceSection.jsx` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/security-architecture/sections/DecisionsSection.jsx` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/security-architecture/sections/FrameworkSection.jsx` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/security-architecture/sections/GenericSection.jsx` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/security-architecture/sections/MitreSection.jsx` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/security-architecture/sections/OverviewSection.jsx` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/security-architecture/sections/ReviewHistorySection.jsx` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/security-architecture/sections/RiskRegisterSection.jsx` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/security-architecture/sections/StaleRecordsSection.jsx` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/security-architecture/sections/ThreatScenariosSection.jsx` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/security-architecture/sections/TrustBoundariesSection.jsx` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/pages/security-architecture/shared/ArchDataGrid.jsx` | `covered` | `fe-admin-shell` | exact path mention in chapter body/chips |
| `frontend/src/scoring/fixtures/threat_parity.json` | `covered` | `ie-scoring` | exact path mention in chapter body/chips |
| `frontend/src/scoring/riskScore.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/scoring/riskScore.test.js` | `out_of_scope` | — | ; FE gate/unit test; aggregate into Testing strategy chapter |
| `frontend/src/styles/tokens.css` | `covered` | `fe-admin-shell`, `fe-design`, `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/utils/activeStateGate.test.js` | `out_of_scope` | — | ; FE gate/unit test; aggregate into Testing strategy chapter |
| `frontend/src/utils/adminLinks.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/utils/adminMode.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/utils/aiAssets.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/utils/apiQueuePresentation.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/utils/apiQueuePresentation.test.js` | `out_of_scope` | — | ; FE gate/unit test; aggregate into Testing strategy chapter |
| `frontend/src/utils/appLinks.js` | `covered` | `fe-analyst-shell`, `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/utils/archAnalystCleanupGate.test.js` | `out_of_scope` | — | ; FE gate/unit test; aggregate into Testing strategy chapter |
| `frontend/src/utils/archLayoutGate.test.js` | `out_of_scope` | — | ; FE gate/unit test; aggregate into Testing strategy chapter |
| `frontend/src/utils/archTabRemovalGate.test.js` | `out_of_scope` | — | ; FE gate/unit test; aggregate into Testing strategy chapter |
| `frontend/src/utils/architectureGraphGate.test.js` | `out_of_scope` | — | ; FE gate/unit test; aggregate into Testing strategy chapter |
| `frontend/src/utils/architectureGraphLayout.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/utils/architectureGraphView.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/utils/architectureGraphView.test.js` | `out_of_scope` | — | ; FE gate/unit test; aggregate into Testing strategy chapter |
| `frontend/src/utils/assetProfileIo.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/utils/authRefreshRaceGate.test.js` | `out_of_scope` | — | ; FE gate/unit test; aggregate into Testing strategy chapter |
| `frontend/src/utils/backendRestart.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/utils/campaignClusterOpen.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/utils/caseStudyFeed.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/utils/chartTheme.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/utils/clearPointerState.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/utils/clearPointerState.test.js` | `out_of_scope` | — | ; FE gate/unit test; aggregate into Testing strategy chapter |
| `frontend/src/utils/correlationPresentation.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/utils/correlationPresentation.test.js` | `out_of_scope` | — | ; FE gate/unit test; aggregate into Testing strategy chapter |
| `frontend/src/utils/cveAge.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/utils/cveFilters.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/utils/dataGridStandardGate.test.js` | `out_of_scope` | — | ; FE gate/unit test; aggregate into Testing strategy chapter |
| `frontend/src/utils/dateTimePickerSimpleGate.test.js` | `out_of_scope` | — | ; FE gate/unit test; aggregate into Testing strategy chapter |
| `frontend/src/utils/dateTimePickerStandardGate.test.js` | `out_of_scope` | — | ; FE gate/unit test; aggregate into Testing strategy chapter |
| `frontend/src/utils/detectLabels.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/utils/detectLabels.test.js` | `out_of_scope` | — | ; FE gate/unit test; aggregate into Testing strategy chapter |
| `frontend/src/utils/displayPrefs.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/utils/displayPrefsCore.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/utils/displayText.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/utils/domainTermTips.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/utils/domainTermTips.test.js` | `out_of_scope` | — | ; FE gate/unit test; aggregate into Testing strategy chapter |
| `frontend/src/utils/domainValidation.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/utils/drawerDatetimeFixes.test.js` | `out_of_scope` | — | ; FE gate/unit test; aggregate into Testing strategy chapter |
| `frontend/src/utils/drawerForgeMitreLinksGate.test.js` | `out_of_scope` | — | ; FE gate/unit test; aggregate into Testing strategy chapter |
| `frontend/src/utils/epssSparkline.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/utils/epssSparkline.test.js` | `out_of_scope` | — | ; FE gate/unit test; aggregate into Testing strategy chapter |
| `frontend/src/utils/exploitationDisplay.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/utils/exploitationDisplay.test.js` | `out_of_scope` | — | ; FE gate/unit test; aggregate into Testing strategy chapter |
| `frontend/src/utils/exportCommon.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/utils/exportCsv.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/utils/exportXlsx.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/utils/extractIndicatorsFromCve.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/utils/feedEpssUiCleanupGate.test.js` | `out_of_scope` | — | ; FE gate/unit test; aggregate into Testing strategy chapter |
| `frontend/src/utils/feedHealthStatus.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/utils/forgeDeadControlsGate.test.js` | `out_of_scope` | — | ; FE gate/unit test; aggregate into Testing strategy chapter |
| `frontend/src/utils/forgeMitreNavigatorGate.test.js` | `out_of_scope` | — | ; FE gate/unit test; aggregate into Testing strategy chapter |
| `frontend/src/utils/forgeUrlTabClearGate.test.js` | `out_of_scope` | — | ; FE gate/unit test; aggregate into Testing strategy chapter |
| `frontend/src/utils/formatIntelLabel.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/utils/formatIntelLabel.test.js` | `out_of_scope` | — | ; FE gate/unit test; aggregate into Testing strategy chapter |
| `frontend/src/utils/heatmapGrid.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/utils/huntPackPdf.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/utils/hybridFeedSearch.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/utils/hybridFeedSearch.test.js` | `out_of_scope` | — | ; FE gate/unit test; aggregate into Testing strategy chapter |
| `frontend/src/utils/iconOnlyAriaGate.test.js` | `out_of_scope` | — | ; FE gate/unit test; aggregate into Testing strategy chapter |
| `frontend/src/utils/intelProvenance.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/utils/investigationActors.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/utils/investigationLabels.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/utils/investigationLabels.test.js` | `out_of_scope` | — | ; FE gate/unit test; aggregate into Testing strategy chapter |
| `frontend/src/utils/investigationPdf.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/utils/iocLookupMessages.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/utils/iocLookupMessages.test.js` | `out_of_scope` | — | ; FE gate/unit test; aggregate into Testing strategy chapter |
| `frontend/src/utils/kevDeadline.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/utils/kevDeadline.test.js` | `out_of_scope` | — | ; FE gate/unit test; aggregate into Testing strategy chapter |
| `frontend/src/utils/keyboardScope.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/utils/keyboardScope.test.js` | `out_of_scope` | — | ; FE gate/unit test; aggregate into Testing strategy chapter |
| `frontend/src/utils/lazyWithReload.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/utils/mitreNavigatorHelpers.test.js` | `out_of_scope` | — | ; FE gate/unit test; aggregate into Testing strategy chapter |
| `frontend/src/utils/momentumCache.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/utils/morningBriefFormat.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/utils/morningBriefFormat.test.js` | `out_of_scope` | — | ; FE gate/unit test; aggregate into Testing strategy chapter |
| `frontend/src/utils/motion.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/utils/motion.test.js` | `out_of_scope` | — | ; FE gate/unit test; aggregate into Testing strategy chapter |
| `frontend/src/utils/nativeRangeGate.test.js` | `out_of_scope` | — | ; FE gate/unit test; aggregate into Testing strategy chapter |
| `frontend/src/utils/nativeSelectGate.test.js` | `out_of_scope` | — | ; FE gate/unit test; aggregate into Testing strategy chapter |
| `frontend/src/utils/navHistory.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/utils/navHistory.test.js` | `out_of_scope` | — | ; FE gate/unit test; aggregate into Testing strategy chapter |
| `frontend/src/utils/notificationChime.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/utils/notificationsApi.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/utils/observableExtraction.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/utils/openCveDrawer.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/utils/patchReferences.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/utils/patchReferences.test.js` | `out_of_scope` | — | ; FE gate/unit test; aggregate into Testing strategy chapter |
| `frontend/src/utils/patchRemediation.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/utils/patchRemediation.test.js` | `out_of_scope` | — | ; FE gate/unit test; aggregate into Testing strategy chapter |
| `frontend/src/utils/pdfAiSummary.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/utils/pdfReport.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/utils/personalizationCopy.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/utils/personalizationCopy.test.js` | `out_of_scope` | — | ; FE gate/unit test; aggregate into Testing strategy chapter |
| `frontend/src/utils/rechartsTheme.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/utils/rechartsVersionGate.test.js` | `out_of_scope` | — | ; FE gate/unit test; aggregate into Testing strategy chapter |
| `frontend/src/utils/referenceRows.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/utils/referenceRows.test.js` | `out_of_scope` | — | ; FE gate/unit test; aggregate into Testing strategy chapter |
| `frontend/src/utils/report.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/utils/safeExternalUrl.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/utils/safeExternalUrl.test.js` | `out_of_scope` | — | ; FE gate/unit test; aggregate into Testing strategy chapter |
| `frontend/src/utils/sectionHeading.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/utils/sectionHeading.test.js` | `out_of_scope` | — | ; FE gate/unit test; aggregate into Testing strategy chapter |
| `frontend/src/utils/sectionLabels.test.js` | `out_of_scope` | — | ; FE gate/unit test; aggregate into Testing strategy chapter |
| `frontend/src/utils/securityArchitecturePdf.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/utils/securityPostureGate.test.js` | `out_of_scope` | — | ; FE gate/unit test; aggregate into Testing strategy chapter |
| `frontend/src/utils/selectionAccentGate.test.js` | `out_of_scope` | — | ; FE gate/unit test; aggregate into Testing strategy chapter |
| `frontend/src/utils/severitySemantics.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/utils/sharedObservables.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/utils/sharedObservables.test.js` | `out_of_scope` | — | ; FE gate/unit test; aggregate into Testing strategy chapter |
| `frontend/src/utils/shellUrlState.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/utils/shellUrlState.test.js` | `out_of_scope` | — | ; FE gate/unit test; aggregate into Testing strategy chapter |
| `frontend/src/utils/stackLocalSync.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/utils/stackLocalSync.test.js` | `out_of_scope` | — | ; FE gate/unit test; aggregate into Testing strategy chapter |
| `frontend/src/utils/timezone.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/utils/tutorial.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/utils/typographyPrefs.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/utils/userPreferences.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `frontend/src/utils/userStack.js` | `covered` | `fe-shared-utils` | exact path mention in chapter body/chips |
| `deploy/briefr-backend.service` | `covered` | `arch-monolith`, `devops-deploy` | exact path mention in chapter body/chips |
| `deploy/briefr-backup.service` | `covered` | `devops-deploy` | exact path mention in chapter body/chips |
| `deploy/briefr-backup.sh` | `covered` | `devops-deploy` | exact path mention in chapter body/chips |
| `deploy/briefr-backup.timer` | `covered` | `devops-deploy` | exact path mention in chapter body/chips |
| `deploy/briefr-doctor.sh` | `covered` | `devops-deploy` | exact path mention in chapter body/chips |
| `deploy/briefr-pg-backup.service` | `covered` | `devops-deploy` | exact path mention in chapter body/chips |
| `deploy/briefr-pg-backup.sh` | `covered` | `devops-deploy` | exact path mention in chapter body/chips |
| `deploy/briefr-pg-backup.timer` | `covered` | `devops-deploy` | exact path mention in chapter body/chips |
| `deploy/briefr-restore.sh` | `covered` | `devops-deploy` | exact path mention in chapter body/chips |
| `deploy/briefr-update.sh` | `covered` | `devops-deploy` | exact path mention in chapter body/chips |
| `deploy/briefr.target` | `covered` | `devops-deploy` | exact path mention in chapter body/chips |
| `deploy/check-backend.sh` | `covered` | `devops-deploy` | exact path mention in chapter body/chips |
| `deploy/docker-compose.postgres.yml` | `covered` | `devops-deploy` | exact path mention in chapter body/chips |
| `deploy/external-postgres.env.example` | `covered` | `devops-deploy` | exact path mention in chapter body/chips |
| `deploy/lib.sh` | `covered` | `devops-deploy` | exact path mention in chapter body/chips |
| `deploy/logrotate-briefr.conf` | `covered` | `devops-deploy` | exact path mention in chapter body/chips |
| `deploy/nginx-briefr-http.conf` | `covered` | `devops-deploy` | exact path mention in chapter body/chips |
| `deploy/nginx-briefr.conf` | `covered` | `devops-deploy` | exact path mention in chapter body/chips |
| `deploy/nginx-snippet-gzip.conf` | `covered` | `devops-deploy` | exact path mention in chapter body/chips |
| `deploy/nginx-snippet-security-headers-https.conf` | `covered` | `devops-deploy` | exact path mention in chapter body/chips |
| `deploy/nginx-snippet-security-headers.conf` | `covered` | `devops-deploy` | exact path mention in chapter body/chips |
| `deploy/setup.sh` | `covered` | `devops-deploy` | exact path mention in chapter body/chips |
| `deploy/smoke-intel.sh` | `covered` | `devops-deploy` | exact path mention in chapter body/chips |
| `backend/db/dialect.py` | `orphan_mention` | `be-data`, `roadmap-reversed` | named in STUDY_GUIDE.html; Path does not exist on disk — likely stale |
| `backend/tests/test_router_split.py` | `covered` | `be-bootstrap` | mentioned; outside primary inventory roots; Exists on disk but not under backend/frontend/src/deploy inventory roots |
| `scripts/build_study_guide_book.py` | `covered` | `preface` | mentioned; outside primary inventory roots; Exists on disk but not under backend/frontend/src/deploy inventory roots |
| `scripts/export_intel_snapshot.py` | `covered` | `be-data` | mentioned; outside primary inventory roots; Exists on disk but not under backend/frontend/src/deploy inventory roots |
| `scripts/generate_security_corpus.py` | `covered` | `api-secarch` | mentioned; outside primary inventory roots; Exists on disk but not under backend/frontend/src/deploy inventory roots |
| `backend/tests/**` | `out_of_scope` | — | ; Aggregate into Testing strategy chapter; not file-mapped |
| `frontend/src/**/*.test.js` | `out_of_scope` | — | ; FE gate/unit tests; aggregate into Testing strategy chapter |
