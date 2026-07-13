# scripts/ — repo tooling (not shipped)

Dev, docs, and release tooling that runs against the repository. Nothing here
runs in production — production-box scripts live in `deploy/`, and app
management scripts (create user, backfill, env sync) live in `backend/scripts/`.

| Script | Purpose | Output |
|--------|---------|--------|
| `verify-local.sh` | Local pre-merge gate mirroring CI (`--full` adds Postgres pytest, gitleaks, Playwright) | exit code |
| `seed_screenshot_data.py` | Seed sample CVEs + warm RSS caches for local dev / captures | database rows |
| `capture_readme_screenshots.mjs` | README screenshots via Playwright | `docs/assets/screenshots/` |
| `capture_theme_screenshots.mjs` | Theme-audit screenshots | `docs/assets/screenshots/theme-audit/` |
| `generate_system_design_pdf.mjs` | Printable architecture doc from `docs/SYSTEM_DESIGN.md` | `SYSTEM_DESIGN.pdf` (gitignored) |
| `generate_technical_inventory_xlsx.py` | Inventory spreadsheet | `TECHNICAL_INVENTORY.xlsx` (gitignored) |
| `generate_architecture_map.py` | Interactive architecture map | `architecture-map.html` (gitignored) |
| `generate_security_corpus.py` | Regenerate `backend/security_architecture/corpus/` generated YAML (drift-tested in CI) | committed corpus files |
| `export_intel_snapshot.py` / `import_intel_snapshot.py` / `verify_intel_snapshot.py` | Public intel bundle per `docs/DATA_SNAPSHOT.md` | `briefr-intel-*.pgdump.gz` |
| `verify_db_parity.py` | SQLite vs Postgres behavior parity checks | report |
| `snapshot_version.py` | Version stamp helper for snapshot docs | stdout |
| `build_gemini_reconciliation.py` | One-off review-bot reconciliation report (historical) | report |
