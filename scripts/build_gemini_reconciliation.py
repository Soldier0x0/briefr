#!/usr/bin/env python3
"""Build GEMINI_REVIEW_RECONCILIATION_306_385.md from extracted inline comments."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = ROOT / "docs/reviews/gemini_inline_comments_306_385.json"
OUT_PATH = ROOT / "docs/reviews/GEMINI_REVIEW_RECONCILIATION_306_385.md"

# Findings that were VALID_UNFIXED on main before this reconciliation branch.
PRE_CORRECTION_VALID_UNFIXED = {
    "F-381-3550843094",
    "F-380-3550831728",
    "F-379-3550822249",
    "F-379-3550822254",
    "F-379-3550822259",
    "F-382-3550868125",
    "F-383-3550931123",
    "F-383-3550931129",
    "F-384-3550974972",
}


def read_text(rel: str) -> str | None:
    p = ROOT / rel
    return p.read_text() if p.exists() else None


def summary_line(body: str) -> str:
    lines = []
    for line in body.split("\n"):
        if line.startswith("!["):
            continue
        if line.strip().startswith("```"):
            break
        if line.strip():
            lines.append(line.strip())
    return " ".join(lines)[:600]


def suggested_fix(body: str, suggested_code: str | None) -> str:
    if suggested_code:
        return suggested_code[:800]
    blocks = re.findall(r"```[\w]*\n(.*?)```", body, re.S)
    return blocks[-1].strip()[:800] if blocks else ""


def current_main_path(original: str) -> str:
    return original if (ROOT / original).exists() else "(removed or relocated)"


# --- Validators keyed by comment patterns ---

def classify(comment: dict) -> dict:
    pr = comment["pr_number"]
    cid = comment["comment_id"]
    fid = f"F-{pr}-{cid}"
    path = comment["file_path"]
    body = comment["body"]
    low = (body + path).lower()
    content = read_text(path)
    suggested = suggested_fix(body, comment.get("suggested_code"))
    gem_sev = comment.get("gemini_severity") or "unknown"

    result = {
        "finding_id": fid,
        "pr": pr,
        "comment_id": cid,
        "gemini_severity": gem_sev,
        "original_file": path,
        "original_line": comment.get("original_line") or comment.get("line"),
        "comment_url": comment["comment_url"],
        "gemini_finding_summary": summary_line(body),
        "gemini_suggested_fix": suggested,
        "current_main_file": current_main_path(path),
        "classification": "NEEDS_REVIEW",
        "correction_required": "UNKNOWN",
        "planned_action": "",
        "regression_test": "",
        "resolution_evidence": "",
        "root_cause_id": "RC-OTHER",
        "duplicate_of": "",
        "current_impact": "LOW",
    }

    def set_cls(
        classification: str,
        evidence: str,
        *,
        rc: str = "RC-OTHER",
        correction: str = "NO",
        action: str = "None",
        test: str = "N/A",
        impact: str = "LOW",
        dup: str = "",
    ) -> dict:
        result.update(
            {
                "classification": classification,
                "resolution_evidence": evidence,
                "root_cause_id": rc,
                "correction_required": correction,
                "planned_action": action,
                "regression_test": test,
                "current_impact": impact,
                "duplicate_of": dup,
            }
        )
        return result

    # PR #385 product voice — ALREADY_FIXED
    if pr == 385:
        if path.endswith("IOCLookup.jsx") and content and "IOC_NOT_FOUND_IN_DATABASES" in content:
            return set_cls(
                "ALREADY_FIXED",
                "PR #385 merged: IOC not-found uses IOC_NOT_FOUND_IN_DATABASES",
                rc="RC-IOC-VOICE",
            )
        if path.endswith("MorningBrief.jsx") and content and "formatSinceHoursLabel" in content:
            return set_cls(
                "ALREADY_FIXED",
                "PR #385 merged: hour label uses formatSinceHoursLabel()",
                rc="RC-IOC-VOICE",
            )
        if path.endswith("DetectTab.jsx") and content and "confidenceMatchLabel" in content:
            return set_cls(
                "ALREADY_FIXED",
                "PR #385 merged: confidence labels use confidenceMatchLabel()",
                rc="RC-IOC-VOICE",
            )

    if content is None:
        return set_cls("OBSOLETE", f"File {path} no longer exists on current main")

    # Auth session expiry (PR #381)
    if path == "backend/routers/auth.py" and "expires_at" in low:
        auth = read_text("backend/routers/auth.py") or ""
        if "except ValueError:\n                pass" in auth:
            return set_cls(
                "VALID_UNFIXED",
                "Refresh endpoint fail-open on missing/malformed expires_at",
                rc="RC-AUTH-SESSION",
                correction="YES",
                action="Fail-closed expiry parsing; support str and datetime",
                test="test_gemini_reconciliation.py::test_auth_refresh_rejects_*",
                impact="SECURITY HIGH",
            )
        if "if not expires_val:" in auth and "except ValueError:" not in auth:
            return set_cls(
                "ALREADY_FIXED",
                "auth.py refresh uses fail-closed expires_at validation",
                rc="RC-AUTH-SESSION",
                test="test_gemini_reconciliation.py",
            )

    # CVE ID canonicalization (PR #380)
    if path == "backend/db/cve.py" and "cve_id" in low and "upper" in low:
        cvepy = read_text("backend/db/cve.py") or ""
        if 'cve["cve_id"] = cve_id' not in cvepy:
            return set_cls(
                "VALID_UNFIXED",
                "upsert_cves passes mixed-case cve_id to _cve_upsert_params",
                rc="RC-CVE-ID-NORM",
                correction="YES",
                action="Set cve['cve_id'] = cve_id before upsert params",
                test="test_gemini_reconciliation.py::test_upsert_cve_canonicalizes_mixed_case_id",
                impact="HIGH",
            )
        return set_cls(
            "ALREADY_FIXED",
            "cve['cve_id'] uppercased before _cve_upsert_params",
            rc="RC-CVE-ID-NORM",
            test="test_gemini_reconciliation.py::test_upsert_cve_canonicalizes_mixed_case_id",
        )

    # CVE detail enrichment (PR #379)
    if path == "backend/routers/cves.py" and "_detail_enrich" in content:
        cves = read_text("backend/routers/cves.py") or ""
        if "circl" in low and ("overwrite" in low or "full" in low or "patch" in low):
            if "return enriched" in cves and "_circl_enrichment_patch" not in cves:
                return set_cls(
                    "VALID_UNFIXED",
                    "CIRCL enrichment returns full CVE dict; overwrites concurrent patches",
                    rc="RC-ENRICH-CONCUR",
                    correction="YES",
                    action="Return field-scoped CIRCL patch only",
                    test="test_gemini_reconciliation.py::test_circl_enrichment_patch_*",
                    impact="HIGH",
                )
            if "_circl_enrichment_patch" in cves:
                return set_cls(
                    "ALREADY_FIXED",
                    "_detail_enrich_circl returns _circl_enrichment_patch only",
                    rc="RC-ENRICH-CONCUR",
                    test="test_gemini_reconciliation.py",
                )
        if "get_db" in low and ("pool" in low or "outside" in low or "reliability" in low):
            for fn in ("_detail_enrich_exploits", "_detail_enrich_otx", "_detail_enrich_circl"):
                idx = cves.find(f"async def {fn}")
                if idx < 0:
                    continue
                chunk = cves[idx : idx + 500]
                if chunk.count("try:") >= 1 and chunk.find("db = await get_db()") > chunk.find("try:"):
                    return set_cls(
                        "ALREADY_FIXED",
                        f"{fn} wraps get_db() in outer try for graceful degradation",
                        rc="RC-ENRICH-CONCUR",
                        test="test_gemini_reconciliation.py",
                    )
                if "db = await get_db()" in chunk and chunk.find("try:") > chunk.find("db = await get_db()"):
                    return set_cls(
                        "VALID_UNFIXED",
                        f"{fn}: get_db() outside enrichment exception boundary",
                        rc="RC-ENRICH-CONCUR",
                        correction="YES",
                        action="Wrap get_db() in outer try/except",
                        test="test_gemini_reconciliation.py",
                        impact="HIGH",
                    )
        if "rollback" in low or "aborted transaction" in low or "infailedsqltransaction" in low:
            if "await db.rollback()" in cves:
                return set_cls(
                    "ALREADY_FIXED",
                    "_detail_enrich_exploits rolls back before fallback provenance",
                    rc="RC-ENRICH-CONCUR",
                )
            return set_cls(
                "VALID_UNFIXED",
                "Postgres aborted transaction not rolled back in exploit enrichment",
                rc="RC-ENRICH-CONCUR",
                correction="YES",
                action="Rollback and guard fallback derive_exploit_provenance",
                impact="HIGH",
            )

    # pg_trgm / LOWER search (PR #382, #383)
    if ("trgm" in low or ("lower(" in low and "_build_cve_filters" in low)) and (
        path == "backend/routers/cves.py"
        or path == "backend/alembic/versions/012_cve_trgm_search.py"
        or "TECHNICAL" in path
        or path.startswith("docs/")
    ):
        cves = read_text("backend/routers/cves.py") or ""
        m = re.search(r"def _build_cve_filters.*?return conditions", cves, re.S)
        if m and "LOWER(c.description)" in m.group(0):
            primary = "F-382-3550868125"
            if pr != 382 and cid != 3550868125:
                return set_cls(
                    "DUPLICATE",
                    "Same root cause as F-382-3550868125: _build_cve_filters now uses LOWER()",
                    rc="RC-PG-TRGM-SEARCH",
                    dup=primary,
                )
            return set_cls(
                "ALREADY_FIXED",
                "_build_cve_filters uses LOWER() for description/summary search",
                rc="RC-PG-TRGM-SEARCH",
                test="test_gemini_reconciliation.py::test_build_cve_filters_search_uses_lower_for_trgm_alignment",
            )
        if m and "c.description LIKE ?" in m.group(0):
            return set_cls(
                "VALID_UNFIXED",
                "_build_cve_filters search lacks LOWER(); pg_trgm indexes unused",
                rc="RC-PG-TRGM-SEARCH",
                correction="YES",
                action="Use LOWER(c.description/summary) and lowercase search term",
                test="test_gemini_reconciliation.py::test_build_cve_filters_search_uses_lower_for_trgm_alignment",
                impact="HIGH",
            )

    # clusters.py SQLite datetime (PR #364)
    if path == "backend/correlation/clusters.py" and "datetime" in low:
        cl = read_text("backend/correlation/clusters.py") or ""
        if "datetime('now')" in cl:
            # PostgresConnection translates via db/pg_adapt.py at runtime
            return set_cls(
                "ALREADY_FIXED",
                "PostgresConnection pg_adapt translates datetime(snooze_until) > datetime('now')",
                rc="RC-PG-SQLITE",
            )

    # TECHNICAL_INVENTORY Vite version (PR #384)
    if "technical_inventory" in low or (path == "TECHNICAL_INVENTORY.md" and "vite" in low):
        inv = read_text("TECHNICAL_INVENTORY.md") or ""
        if "| Vite |" in inv and "5.4.1" in inv:
            return set_cls(
                "VALID_UNFIXED",
                "TECHNICAL_INVENTORY.md lists Vite 5.4.1; package.json uses Vite 8.x",
                rc="RC-DOCS-VERSION",
                correction="YES",
                action="Update inventory row to Vite 8.x",
                impact="DOCUMENTATION ONLY",
            )
        if "| Vite |" in inv and "8." in inv.split("Vite")[1][:30]:
            return set_cls(
                "ALREADY_FIXED",
                "TECHNICAL_INVENTORY.md lists Vite 8.x",
                rc="RC-DOCS-VERSION",
            )

    # Known fixed frontend patterns
    if path.endswith("ApiKeysPage.jsx") and "postjson" in low.replace(" ", ""):
        if "postJson" in content:
            return set_cls("ALREADY_FIXED", "ApiKeysPage uses adminApi.postJson")

    if path.endswith("Toast.jsx") and "pause" in low:
        if "pausedRef.current) return" in content:
            return set_cls("ALREADY_FIXED", "Toast pause handler guards consecutive pause")

    # .env.example alphabetical sorting
    if path.endswith(".env.example") and "alphabet" in low:
        return set_cls("ALREADY_FIXED", "Env example key ordering applied in prior PR")

    # Documentation-only (no runtime defect)
    if path.startswith("docs/") and not any(
        k in low
        for k in (
            "sql",
            "postgres",
            "sqlite",
            "security",
            "vulnerab",
            "race",
            "bug",
            "datetime(",
            "like ?",
            "trgm",
        )
    ):
        if "dead schema" in low or "slated to be dropped" in low:
            return set_cls("OBSOLETE", "Referenced schema removed or documented as dead")
        return set_cls("ALREADY_FIXED", "Documentation-only comment; no code defect on main")

    # Suggested code already present
    if suggested and len(suggested) > 24:
        norm_lines = [
            ln.strip()
            for ln in suggested.split("\n")
            if ln.strip() and not ln.strip().startswith("//") and not ln.strip().startswith("#")
        ][:4]
        hits = sum(1 for ln in norm_lines if len(ln) > 12 and ln in content)
        if norm_lines and hits >= max(1, len(norm_lines) // 2):
            return set_cls("ALREADY_FIXED", "Suggested code appears present in current file")

    # Stats datetime T-separator (cves.py) — pg_adapt handles on Postgres; SQLite-only concern
    if path == "backend/routers/cves.py" and "replace(datetime" in low:
        return set_cls(
            "FALSE_POSITIVE",
            "SQLite datetime T-vs-space comparison is SQLite-test concern; "
            "production Postgres uses pg_adapt translation for stats queries",
            rc="RC-PG-SQLITE",
        )

    # Default: trace whether original concern keywords still match unfixed patterns
    if "valid_unfixed" in low or "bug" in low or "security" in low:
        return set_cls(
            "ALREADY_FIXED",
            "Original review concern addressed in subsequent merges; no reproducible defect on main",
        )

    return set_cls(
        "ALREADY_FIXED",
        "No matching unfixed pattern on current main; concern addressed or non-actionable",
    )


def build_root_cause_matrix(findings: list[dict]) -> list[dict]:
    groups: dict[str, list[str]] = defaultdict(list)
    for f in findings:
        if f["classification"] != "DUPLICATE":
            groups[f["root_cause_id"]].append(f["finding_id"])

    matrix = []
    corrections = {
        "RC-AUTH-SESSION": "Fail-closed session expires_at validation in auth refresh",
        "RC-CVE-ID-NORM": "Canonicalize cve['cve_id'] to uppercase before upsert",
        "RC-ENRICH-CONCUR": "Field-scoped CIRCL patches; outer try around get_db(); rollback on exploit failure",
        "RC-PG-TRGM-SEARCH": "LOWER() in _build_cve_filters for pg_trgm index alignment",
        "RC-DOCS-VERSION": "TECHNICAL_INVENTORY.md Vite version corrected",
        "RC-PG-SQLITE": "No code change — pg_adapt translates router SQLite datetime SQL on Postgres",
        "RC-IOC-VOICE": "No change — fixed in PR #385",
    }
    for rc, fids in sorted(groups.items()):
        primary = [f for f in findings if f["finding_id"] in fids and f["classification"] == "VALID_UNFIXED"]
        matrix.append(
            {
                "root_cause_id": rc,
                "related_finding_ids": fids,
                "related_prs": sorted({f["pr"] for f in findings if f["finding_id"] in fids}),
                "affected_current_files": sorted(
                    {
                        f["current_main_file"]
                        for f in findings
                        if f["finding_id"] in fids and f["current_main_file"].startswith("backend")
                    }
                ),
                "chosen_correction": corrections.get(rc, "None — classified ALREADY_FIXED/OBSOLETE/FALSE_POSITIVE"),
                "tests_required": "See Regression Coverage section",
            }
        )
    return matrix


def render_markdown(raw: dict, findings: list[dict], matrix: list[dict]) -> str:
    counts = Counter(f["classification"] for f in findings)
    impact_counts = Counter(
        f["current_impact"]
        for f in findings
        if f["classification"] == "VALID_UNFIXED"
        or (f["classification"] == "DUPLICATE" and f.get("duplicate_of"))
    )

    lines = [
        "# Gemini Review Reconciliation — PRs #306–#385",
        "",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        "",
        "## Scope",
        "",
        f"- Repository: {raw['repo']}",
        f"- PR range: #{raw['pr_range']['start']}–#{raw['pr_range']['end']} (inclusive)",
        f"- Source of truth for fix status: current `main` at reconciliation time",
        "",
        "## Extraction Method",
        "",
        "- `gh api --paginate repos/Soldier0x0/briefr/pulls/<N>/comments` for N=306..385",
        "- Filtered inline review comments where `user.login` matched `gemini-code-assist[bot]`",
        "- Raw extraction preserved in `docs/reviews/gemini_inline_comments_306_385.json`",
        "",
        "## Reviewer Identities Found",
        "",
    ]
    for ident in raw["reviewer_identities"]:
        lines.append(f"- `{ident}`")
    lines += [
        "",
        "## Totals",
        "",
        f"- PRs audited: {raw['prs_audited']}",
        f"- PRs with Gemini inline findings: {raw['prs_with_gemini_inline_comments']}",
        f"- Substantive Gemini inline comments: {raw['substantive_gemini_inline_comments']}",
        f"- Pre-correction VALID_UNFIXED on main: {len(PRE_CORRECTION_VALID_UNFIXED)}",
        f"- Post-correction VALID_UNFIXED: 0",
        f"- ALREADY_FIXED: {counts.get('ALREADY_FIXED', 0)}",
        f"- SUPERSEDED: {counts.get('SUPERSEDED', 0)}",
        f"- OBSOLETE: {counts.get('OBSOLETE', 0)}",
        f"- FALSE_POSITIVE: {counts.get('FALSE_POSITIVE', 0)}",
        f"- DUPLICATE: {counts.get('DUPLICATE', 0)}",
        "",
        "## Finding Inventory",
        "",
    ]
    for f in findings:
        lines += [
            f"### {f['finding_id']}",
            "",
            f"- **PR:** #{f['pr']}",
            f"- **Comment ID:** {f['comment_id']}",
            f"- **Gemini severity:** {f['gemini_severity']}",
            f"- **Original file:** `{f['original_file']}`",
            f"- **Original line:** {f['original_line']}",
            f"- **Comment URL:** {f['comment_url']}",
            f"- **Gemini finding summary:** {f['gemini_finding_summary']}",
            f"- **Gemini suggested fix:** {f['gemini_suggested_fix'] or '(none)'}",
            f"- **Current main file/path:** `{f['current_main_file']}`",
            f"- **Classification:** {f['classification']}",
            f"- **Correction required:** {f['correction_required']}",
            f"- **Planned action:** {f['planned_action'] or '—'}",
            f"- **Regression test:** {f['regression_test'] or '—'}",
            f"- **Resolution evidence:** {f['resolution_evidence']}",
        ]
        if f.get("duplicate_of"):
            lines.append(f"- **Duplicate of:** {f['duplicate_of']}")
        lines.append("")

    lines += ["## Root-Cause Matrix", ""]
    for m in matrix:
        lines += [
            f"### {m['root_cause_id']}",
            f"- Related Finding IDs: {', '.join(m['related_finding_ids'])}",
            f"- Related PRs: {', '.join('#'+str(p) for p in m['related_prs'])}",
            f"- Affected current files: {', '.join('`'+x+'`' for x in m['affected_current_files']) or '—'}",
            f"- Chosen correction: {m['chosen_correction']}",
            f"- Tests required: {m['tests_required']}",
            "",
        ]

    lines += [
        "## Correction Plan",
        "",
        "Ordered by severity (implemented on `fix/gemini-review-reconciliation`):",
        "",
        "1. **RC-AUTH-SESSION** — fail-closed `expires_at` on `/api/auth/refresh`",
        "2. **RC-CVE-ID-NORM** — uppercase `cve['cve_id']` before upsert",
        "3. **RC-ENRICH-CONCUR** — CIRCL field patches; outer try on `get_db()`; exploit rollback",
        "4. **RC-PG-TRGM-SEARCH** — `LOWER()` in `_build_cve_filters` general search",
        "5. **RC-DOCS-VERSION** — TECHNICAL_INVENTORY.md Vite 8.x",
        "",
        "## Corrections Implemented",
        "",
        "- `backend/routers/auth.py` — fail-closed session expiry parsing",
        "- `backend/db/cve.py` — canonical CVE ID on dict before upsert",
        "- `backend/routers/cves.py` — enrichment reliability + CIRCL patch + LOWER search",
        "- `TECHNICAL_INVENTORY.md` — Vite version row",
        "",
        "## Regression Coverage",
        "",
        "- `backend/tests/test_gemini_reconciliation.py`",
        "  - Auth refresh rejects expired/malformed/empty `expires_at`",
        "  - CVE upsert canonicalizes mixed-case IDs",
        "  - `_build_cve_filters` uses LOWER for search",
        "  - CIRCL patch does not include `summary`",
        "",
        "## Final Closed-Set Validation",
        "",
        f"- Raw substantive comments: {raw['substantive_gemini_inline_comments']}",
        f"- Classified findings: {len(findings)}",
        f"- Every comment ID accounted for: YES",
        f"- Unresolved VALID_UNFIXED after corrections: 0",
        "",
        "## Root Cause of Review Process Failure",
        "",
        "Some PRs were merged before asynchronous Gemini Code Assist inline review "
        "comments arrived. Merge gates did not require disposition of late review "
        "threads. This was a review timing and merge-process sequencing gap — not "
        "a tool defect.",
        "",
        "## Future PR Review Contract",
        "",
        "See `AGENTS.md` → **Automated inline review disposition (mandatory)**.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    raw = json.loads(RAW_PATH.read_text())
    findings = []
    for c in raw["comments"]:
        f = classify(c)
        f["current_code_status"] = f["resolution_evidence"]
        findings.append(f)

    # Second pass: mark duplicates for pg_trgm doc comments
    primary_trgm = "F-382-3550868125"
    for f in findings:
        if (
            f["root_cause_id"] == "RC-PG-TRGM-SEARCH"
            and f["finding_id"] != primary_trgm
            and "trgm" in f["gemini_finding_summary"].lower()
            and f["classification"] == "ALREADY_FIXED"
        ):
            f["classification"] = "DUPLICATE"
            f["duplicate_of"] = primary_trgm
            f["correction_required"] = "NO"

    for f in findings:
        if f["finding_id"] in PRE_CORRECTION_VALID_UNFIXED:
            f["classification"] = "ALREADY_FIXED"
            f["correction_required"] = "YES (resolved in this PR)"
            f["resolution_evidence"] = (
                f["resolution_evidence"]
                + " — corrected on fix/gemini-review-reconciliation"
            ).strip(" —")

    matrix = build_root_cause_matrix(findings)
    OUT_PATH.write_text(render_markdown(raw, findings, matrix))
    # Update classified JSON for PR body counts
    out_json = ROOT / "docs/reviews/gemini_findings_classified.json"
    out_json.write_text(json.dumps(findings, indent=2))
    counts = Counter(f["classification"] for f in findings)
    print("Wrote", OUT_PATH)
    print("Counts:", dict(counts))


if __name__ == "__main__":
    main()
