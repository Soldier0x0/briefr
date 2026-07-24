# Exported documentation images

Place **PNG** (2×) or **SVG** files here. Filenames must match [`IMAGE_BRIEFS.md`](../IMAGE_BRIEFS.md).

| File | Status |
|------|--------|
| `briefr-docs-tokens.css` | Shared dark palette for the public docs site |
| `placeholder-diagram.svg` | Generic placeholder for new ADR/concept templates only |
| `production-architecture.svg` | Shipped |
| `auth-layers.svg` | Shipped |
| `correlation-pipeline.svg` | Shipped |
| `ingest-pipeline.svg` | Shipped |
| `adr-001-intel-app-split.svg` | Shipped (ADR-001) |
| `screenshots/*.png` | UI captures (README + USE.md) |
| `ui-brief-tab.png` … `ui-admin-security.png` | Aliases for IMAGE_BRIEFS §11–15 |

**Workflow:** create or export asset → save here → update doc `![...]()` path → mark **Done** in `IMAGE_BRIEFS.md` checklist.

**Regenerate UI screenshots:** `SCREENSHOT_PASSWORD` + `node scripts/capture_readme_screenshots.mjs` (see README).

**Docs site palette:** edit `briefr-docs-tokens.css` when syncing token changes to https://docs.projectjupiter.in
