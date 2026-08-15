"""Backward-compatibility shim — import from db.* submodules directly for new code.

database.py was split into backend/db/ (Phase 3 refactor). Every
function moved verbatim; this file only re-exports so the 35+ existing
`from database import ...` call sites keep working unchanged.
"""
import os

from db.init import get_db, init_db, run_postgres_migrations
from db.cve import *
from db.embeddings_store import (
    embeddings_pgvector_writes_enabled,
    get_cves_needing_embeddings,
    get_cves_needing_embeddings_by_ids,
    upsert_cve_embedding_row,
)
from db.enrichment import *
from db.cache import *
from db.cache_retention import (
    purge_old_ai_operation_payloads,
    purge_old_ai_operations,
    purge_old_audit_log,
    purge_old_cve_change_history,
    purge_old_epss_history,
    purge_old_webhook_delivery_log,
    purge_stale_feed_cache,
    purge_stale_ioc_cache,
    run_retention_cleanup,
)
from db.correlation import *
from db.watchlist import *
from db.ioc_watchlist import *
from db.sync_state import *
from db.app_settings import *
from db.metadata import *
from db.webhooks import *
from db.ai_operations import *
from db.ai_operation_payloads import *

# Re-export constants (also covered by the star-imports above; explicit here
# for discoverability, per the Phase 3 refactor shim template).
from db.sync_state import NVD_SYNC_WATERMARK_KEY, EPSS_BACKFILL_DONE_KEY, ATLAS_UPSTREAM_VERSION_KEY

# Private names imported directly by name from outside this module (grepped
# across backend/ before the split) — `import *` drops underscore-prefixed
# names, so these need an explicit re-export or their callers break:
# - routers/admin.py: from database import _webhook_alert_types
# - tests/test_kev_fields.py: from database import _clean_iso_date
# - tests/test_epss_change_noise.py: from database import _epss_scores_differ
from db.webhooks import _webhook_alert_types
from db.enrichment import _clean_iso_date, _epss_scores_differ
