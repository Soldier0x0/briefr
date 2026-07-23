"""SigmaHQ local Postgres rule index — download, parse, upsert, watermark.

Scheduler job ``sigmahq_index_sync`` (U2) calls :func:`sync_sigmahq_index`.
Detect/Forge read paths (U3/U4) call :func:`find_index_rules_for_cve`.

Postgres-native only. No LLM. Sigma rules only (DRL-1.1 attribution).
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
import os
import re
import tarfile
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import UUID

import yaml

from db.types import DbConnection
from feeds.file_identity import (
    SIGMAHQ_ARCHIVE_IDENTITY_KEY,
    clear_file_identity,
    commit_identity_matches,
    get_file_identity,
    identity_matches,
    set_file_identity,
    sha256_bytes,
)
from resilient_client import resilient_get

logger = logging.getLogger(__name__)

SIGMAHQ_REPO = "SigmaHQ/sigma"
SIGMAHQ_DEFAULT_REF = "master"
SOURCE = "sigmahq"
LICENSE_ID = "DRL-1.1"
LICENSE_URL = (
    "https://github.com/SigmaHQ/Detection-Rule-License/"
    "blob/main/LICENSE.Detection.Rules.md"
)
MAX_RULE_BYTES = 256 * 1024
BATCH_SIZE = 100

RULE_TREE_PREFIXES = (
    "rules/",
    "rules-emerging-threats/",
    "rules-threat-hunting/",
    "rules-compliance/",
)

_CVE_RE = re.compile(r"CVE-\d{4}-\d{4,}", re.IGNORECASE)
_CVE_TAG_RE = re.compile(r"^cve\.(\d{4})\.(\d+)$", re.IGNORECASE)
_CVE_SLUG_RE = re.compile(r"cve[_-]?(\d{4})[_-]?(\d{4,})", re.IGNORECASE)
_ATTACK_TAG_RE = re.compile(
    r"^attack\.t(\d{4})(?:\.(\d{3}))?$", re.IGNORECASE
)
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

ProgressCallback = Callable[[str], None]


@dataclass
class ParsedRule:
    repo_path: str
    rule_uid: str
    title: str
    status: str
    author: str
    description: str
    level: str | None
    rule_family: str
    tags: list[Any]
    references: list[Any]
    logsource: dict[str, Any] | None
    content_yaml: str
    content_sha256: str
    commit_sha: str
    html_url: str
    cve_ids: list[str] = field(default_factory=list)
    technique_ids: list[str] = field(default_factory=list)


@dataclass
class ApplyStats:
    seen: int = 0
    upserted: int = 0
    skipped_unchanged: int = 0
    parse_errors: int = 0
    retired: int = 0
    failed: bool = False
    error: str = ""


@dataclass
class SyncResult:
    status: str  # applied | skipped_commit | skipped_sha | failed
    commit_sha: str = ""
    archive_sha256: str = ""
    stats: ApplyStats = field(default_factory=ApplyStats)
    message: str = ""


def _gh_headers() -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "briefr-sigmahq-index",
    }
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def rule_family_from_path(repo_path: str) -> str:
    p = repo_path.replace("\\", "/")
    if p.startswith("rules-emerging-threats/"):
        return "emerging"
    if p.startswith("rules-threat-hunting/"):
        return "hunting"
    if p.startswith("rules-compliance/"):
        return "compliance"
    return "rules"


def is_rule_path(repo_path: str) -> bool:
    p = repo_path.replace("\\", "/").lstrip("./")
    if not (p.endswith(".yml") or p.endswith(".yaml")):
        return False
    return any(p.startswith(prefix) for prefix in RULE_TREE_PREFIXES)


def strip_archive_root(member_name: str) -> str | None:
    """``sigma-<sha>/rules/...`` → ``rules/...``."""
    name = member_name.replace("\\", "/").lstrip("./")
    if "/" not in name:
        return None
    _root, _, rest = name.partition("/")
    return rest or None


def rule_uid_for(repo_path: str, raw_id: Any) -> str:
    if isinstance(raw_id, str) and _UUID_RE.match(raw_id.strip()):
        try:
            return str(UUID(raw_id.strip()))
        except ValueError:
            pass
    digest = hashlib.sha256(repo_path.encode("utf-8")).hexdigest()
    return digest[:32]


def _normalize_author(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        parts = [str(v).strip() for v in value if str(v).strip()]
        return ", ".join(parts)
    return str(value).strip()


def extract_cve_ids(
    *,
    tags: list[Any],
    references: list[Any],
    title: str,
    description: str,
    repo_path: str,
) -> list[str]:
    found: set[str] = set()
    for tag in tags:
        if not isinstance(tag, str):
            continue
        m = _CVE_TAG_RE.match(tag.strip())
        if m:
            found.add(f"CVE-{m.group(1)}-{m.group(2)}")
    blob_parts = [title or "", description or ""]
    for ref in references:
        if isinstance(ref, str):
            blob_parts.append(ref)
        elif isinstance(ref, dict):
            blob_parts.append(str(ref.get("url") or ref.get("href") or ""))
    blob = "\n".join(blob_parts)
    for m in _CVE_RE.finditer(blob):
        found.add(m.group(0).upper())
    for m in _CVE_SLUG_RE.finditer(repo_path.replace("\\", "/")):
        found.add(f"CVE-{m.group(1)}-{m.group(2)}")
    return sorted(found)


def extract_technique_ids(tags: list[Any]) -> list[str]:
    found: set[str] = set()
    for tag in tags:
        if not isinstance(tag, str):
            continue
        m = _ATTACK_TAG_RE.match(tag.strip())
        if not m:
            continue
        tid = f"T{m.group(1)}"
        if m.group(2):
            tid = f"{tid}.{m.group(2)}"
        found.add(tid)
    return sorted(found)


def html_url_for(commit_sha: str, repo_path: str) -> str:
    return f"https://github.com/{SIGMAHQ_REPO}/blob/{commit_sha}/{repo_path}"


def parse_sigma_file(
    *,
    repo_path: str,
    content: str,
    commit_sha: str,
    content_bytes: bytes | None = None,
) -> ParsedRule | None:
    raw = content_bytes if content_bytes is not None else content.encode("utf-8")
    if len(raw) > MAX_RULE_BYTES:
        logger.warning("Skip oversized Sigma rule path=%s size=%d", repo_path, len(raw))
        return None
    try:
        data = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        logger.warning("Skip corrupt Sigma YAML path=%s: %s", repo_path, exc)
        return None
    if not isinstance(data, dict):
        logger.warning("Skip non-mapping Sigma YAML path=%s", repo_path)
        return None
    if "detection" not in data and "logsource" not in data:
        # Likely not a detection rule (config / meta).
        return None

    tags = data.get("tags") if isinstance(data.get("tags"), list) else []
    refs = data.get("references") if isinstance(data.get("references"), list) else []
    logsource = data.get("logsource") if isinstance(data.get("logsource"), dict) else None
    title = str(data.get("title") or "").strip()
    description = str(data.get("description") or "").strip()
    status = str(data.get("status") or "experimental").strip() or "experimental"
    level = data.get("level")
    level_s = str(level).strip() if level is not None else None
    author = _normalize_author(data.get("author"))
    cves = extract_cve_ids(
        tags=tags,
        references=refs,
        title=title,
        description=description,
        repo_path=repo_path,
    )
    techniques = extract_technique_ids(tags)
    return ParsedRule(
        repo_path=repo_path,
        rule_uid=rule_uid_for(repo_path, data.get("id")),
        title=title,
        status=status,
        author=author,
        description=description,
        level=level_s,
        rule_family=rule_family_from_path(repo_path),
        tags=tags,
        references=refs,
        logsource=logsource,
        content_yaml=content,
        content_sha256=sha256_bytes(raw),
        commit_sha=commit_sha,
        html_url=html_url_for(commit_sha, repo_path),
        cve_ids=cves,
        technique_ids=techniques,
    )


def iter_rule_files(root: Path) -> list[Path]:
    files: list[Path] = []
    if not root.is_dir():
        return files
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        try:
            rel = path.relative_to(root).as_posix()
        except ValueError:
            continue
        if is_rule_path(rel):
            files.append(path)
    return files


def _progress(cb: ProgressCallback | None, message: str) -> None:
    if cb:
        try:
            cb(message)
        except Exception:
            logger.debug("progress callback failed", exc_info=True)


async def resolve_tip_commit(*, ref: str = SIGMAHQ_DEFAULT_REF) -> str | None:
    url = f"https://api.github.com/repos/{SIGMAHQ_REPO}/commits/{ref}"
    try:
        resp = await resilient_get(
            "github",
            url,
            headers=_gh_headers(),
            timeout=30.0,
            retries=1,
            queue_operation="sigmahq_index_sync",
            queue_context_type="task",
            queue_context_id="sigmahq_index_sync",
        )
        data = resp.json()
        sha = (data.get("sha") or "").strip()
        return sha if len(sha) >= 40 else None
    except Exception as exc:
        logger.warning("SigmaHQ tip commit resolve failed: %s", exc)
        return None


async def download_archive(commit_sha: str) -> tuple[bytes, str] | tuple[None, None]:
    url = f"https://codeload.github.com/{SIGMAHQ_REPO}/tar.gz/{commit_sha}"
    try:
        resp = await resilient_get(
            "github",
            url,
            headers=_gh_headers(),
            timeout=120.0,
            retries=1,
            queue_operation="sigmahq_index_sync",
            queue_context_type="task",
            queue_context_id="sigmahq_index_sync",
        )
        raw = resp.content
        if not raw:
            return None, None
        return raw, sha256_bytes(raw)
    except Exception as exc:
        logger.warning("SigmaHQ archive download failed: %s", exc)
        return None, None


def extract_archive_to(archive_bytes: bytes, dest: Path) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:gz") as tar:
        # Python 3.12+: filter='data' when available
        try:
            tar.extractall(dest, filter="data")
        except TypeError:
            tar.extractall(dest)
    # Prefer the single top-level directory GitHub archives use.
    children = [p for p in dest.iterdir() if p.is_dir()]
    if len(children) == 1:
        return children[0]
    return dest


_UPSERT_SQL = """
INSERT INTO detection_rules (
    source, repo_path, rule_uid, title, status, author, description,
    level, rule_family, tags, "references", logsource,
    content_yaml, content_sha256, commit_sha,
    license_id, license_url, html_url, retired_at, updated_at
) VALUES (
    $1, $2, $3, $4, $5, $6, $7,
    $8, $9, $10::jsonb, $11::jsonb, $12::jsonb,
    $13, $14, $15,
    $16, $17, $18, NULL, now()
)
ON CONFLICT (source, repo_path) DO UPDATE SET
    rule_uid = EXCLUDED.rule_uid,
    title = EXCLUDED.title,
    status = EXCLUDED.status,
    author = EXCLUDED.author,
    description = EXCLUDED.description,
    level = EXCLUDED.level,
    rule_family = EXCLUDED.rule_family,
    tags = EXCLUDED.tags,
    "references" = EXCLUDED."references",
    logsource = EXCLUDED.logsource,
    content_yaml = EXCLUDED.content_yaml,
    content_sha256 = EXCLUDED.content_sha256,
    commit_sha = EXCLUDED.commit_sha,
    license_id = EXCLUDED.license_id,
    license_url = EXCLUDED.license_url,
    html_url = EXCLUDED.html_url,
    retired_at = NULL,
    updated_at = now()
WHERE detection_rules.content_sha256 IS DISTINCT FROM EXCLUDED.content_sha256
   OR detection_rules.commit_sha IS DISTINCT FROM EXCLUDED.commit_sha
   OR detection_rules.retired_at IS NOT NULL
RETURNING id, (xmax = 0) AS inserted
"""


async def _upsert_rule(db: DbConnection, rule: ParsedRule) -> int | None:
    """Upsert one rule; return rule id (fetch when RETURNING skipped unchanged)."""
    tags_json = json.dumps(rule.tags)
    refs_json = json.dumps(rule.references)
    log_json = json.dumps(rule.logsource) if rule.logsource is not None else None
    rows = await db.execute_fetchall(
        _UPSERT_SQL,
        (
            SOURCE,
            rule.repo_path,
            rule.rule_uid,
            rule.title,
            rule.status,
            rule.author,
            rule.description,
            rule.level,
            rule.rule_family,
            tags_json,
            refs_json,
            log_json,
            rule.content_yaml,
            rule.content_sha256,
            rule.commit_sha,
            LICENSE_ID,
            LICENSE_URL,
            rule.html_url,
        ),
    )
    if rows:
        return int(rows[0]["id"])
    # Unchanged — still need id for link refresh / seen set.
    existing = await db.execute_fetchall(
        "SELECT id FROM detection_rules WHERE source = $1 AND repo_path = $2",
        (SOURCE, rule.repo_path),
    )
    if not existing:
        return None
    return int(existing[0]["id"])


async def _replace_links(
    db: DbConnection,
    rule_id: int,
    *,
    cve_ids: list[str],
    technique_ids: list[str],
) -> None:
    await db.execute("DELETE FROM detection_rule_cves WHERE rule_id = $1", (rule_id,))
    await db.execute(
        "DELETE FROM detection_rule_techniques WHERE rule_id = $1", (rule_id,)
    )
    for cve_id in cve_ids:
        await db.execute(
            """
            INSERT INTO detection_rule_cves (rule_id, cve_id, match_basis)
            VALUES ($1, $2, 'cve_exact')
            ON CONFLICT DO NOTHING
            """,
            (rule_id, cve_id),
        )
    for tid in technique_ids:
        await db.execute(
            """
            INSERT INTO detection_rule_techniques (rule_id, technique_id)
            VALUES ($1, $2)
            ON CONFLICT DO NOTHING
            """,
            (rule_id, tid),
        )


async def apply_rules_from_dir(
    db: DbConnection,
    root: Path,
    commit_sha: str,
    *,
    progress_callback: ProgressCallback | None = None,
    fail_on_parse_errors: bool = False,
) -> ApplyStats:
    """Parse + upsert + soft-retire from an extracted (or fixture) tree.

    Watermark is **not** written here — caller sets identity after success.
    """
    stats = ApplyStats()
    files = iter_rule_files(root)
    seen_paths: set[str] = set()
    batch = 0

    for path in files:
        rel = path.relative_to(root).as_posix()
        try:
            raw = path.read_bytes()
            text = raw.decode("utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            logger.warning("Skip unreadable Sigma path=%s: %s", rel, exc)
            stats.parse_errors += 1
            continue
        rule = parse_sigma_file(
            repo_path=rel, content=text, commit_sha=commit_sha, content_bytes=raw
        )
        if rule is None:
            # Corrupt YAML counts as parse error; non-rule files ignored quietly
            # if yaml loaded but no detection — treat oversized/corrupt as errors.
            try:
                yaml.safe_load(text)
                # Valid YAML but not a rule — ignore.
            except yaml.YAMLError:
                stats.parse_errors += 1
            continue

        stats.seen += 1
        seen_paths.add(rel)
        try:
            # Detect whether content would change before upsert for stats.
            prior = await db.execute_fetchall(
                """
                SELECT content_sha256, retired_at FROM detection_rules
                WHERE source = $1 AND repo_path = $2
                """,
                (SOURCE, rel),
            )
            rule_id = await _upsert_rule(db, rule)
            if rule_id is None:
                stats.parse_errors += 1
                continue
            await _replace_links(
                db, rule_id, cve_ids=rule.cve_ids, technique_ids=rule.technique_ids
            )
            if prior and prior[0]["content_sha256"] == rule.content_sha256 and prior[0].get("retired_at") is None:
                stats.skipped_unchanged += 1
            else:
                stats.upserted += 1
            batch += 1
            if batch >= BATCH_SIZE:
                await db.commit()
                batch = 0
                _progress(progress_callback, f"SigmaHQ index: upserted {stats.seen} rules…")
        except Exception as exc:
            logger.exception("SigmaHQ upsert failed path=%s: %s", rel, exc)
            stats.failed = True
            stats.error = str(exc)
            try:
                await db.rollback()
            except Exception:
                pass
            return stats

    if batch:
        await db.commit()

    if fail_on_parse_errors and stats.parse_errors:
        stats.failed = True
        stats.error = f"{stats.parse_errors} parse error(s)"
        return stats

    # Soft-retire paths not seen in this apply.
    try:
        active = await db.execute_fetchall(
            """
            SELECT id, repo_path FROM detection_rules
            WHERE source = $1 AND retired_at IS NULL
            """,
            (SOURCE,),
        )
        for row in active:
            if row["repo_path"] not in seen_paths:
                await db.execute(
                    """
                    UPDATE detection_rules
                    SET retired_at = now(), updated_at = now()
                    WHERE id = $1
                    """,
                    (row["id"],),
                )
                stats.retired += 1
        await db.commit()
    except Exception as exc:
        logger.exception("SigmaHQ retire pass failed: %s", exc)
        stats.failed = True
        stats.error = str(exc)
        try:
            await db.rollback()
        except Exception:
            pass
        return stats

    return stats


async def sync_sigmahq_index(
    db: DbConnection,
    *,
    force: bool = False,
    progress_callback: ProgressCallback | None = None,
    tip_commit: str | None = None,
    archive_bytes: bytes | None = None,
    extract_root: Path | None = None,
) -> SyncResult:
    """Full sync: resolve tip → watermark skip → download → apply → set identity.

    Test hooks: pass ``tip_commit`` + ``archive_bytes`` or ``extract_root`` to
    bypass network.
    """
    _progress(progress_callback, "SigmaHQ index: resolving tip commit…")
    commit_sha = tip_commit or await resolve_tip_commit()
    if not commit_sha:
        return SyncResult(status="failed", message="Could not resolve SigmaHQ tip commit")

    stored = await get_file_identity(db, SIGMAHQ_ARCHIVE_IDENTITY_KEY)
    if (
        not force
        and extract_root is None
        and archive_bytes is None
        and commit_identity_matches(stored, commit_sha=commit_sha)
    ):
        return SyncResult(
            status="skipped_commit",
            commit_sha=commit_sha,
            archive_sha256=(stored or {}).get("sha256") or "",
            message="Tip commit unchanged — skip download/apply",
        )

    digest = ""
    root: Path | None = extract_root
    tmp_ctx = None
    try:
        if root is None:
            if archive_bytes is None:
                _progress(progress_callback, "SigmaHQ index: downloading archive…")
                archive_bytes, digest = await download_archive(commit_sha)
                if archive_bytes is None or not digest:
                    return SyncResult(
                        status="failed",
                        commit_sha=commit_sha,
                        message="Archive download failed",
                    )
            else:
                digest = sha256_bytes(archive_bytes)

            if (
                not force
                and stored
                and identity_matches(stored, sha256=digest)
                and commit_identity_matches(stored, commit_sha=commit_sha)
            ):
                # Refresh synced_at only.
                await set_file_identity(
                    db,
                    SIGMAHQ_ARCHIVE_IDENTITY_KEY,
                    sha256=digest,
                    commit_sha=commit_sha,
                    synced_at=_utcnow_iso(),
                    score_date=None,
                )
                await db.commit()
                return SyncResult(
                    status="skipped_sha",
                    commit_sha=commit_sha,
                    archive_sha256=digest,
                    message="Archive sha256 unchanged — skip parse/apply",
                )

            tmp_ctx = tempfile.TemporaryDirectory(prefix="sigmahq-")
            dest = Path(tmp_ctx.name)
            _progress(progress_callback, "SigmaHQ index: extracting archive…")
            root = extract_archive_to(archive_bytes, dest)
        else:
            digest = digest or (stored or {}).get("sha256") or f"fixture:{commit_sha}"

        _progress(progress_callback, "SigmaHQ index: upserting rules…")
        stats = await apply_rules_from_dir(
            db, root, commit_sha, progress_callback=progress_callback
        )
        if stats.failed:
            return SyncResult(
                status="failed",
                commit_sha=commit_sha,
                archive_sha256=digest,
                stats=stats,
                message=stats.error or "Apply failed",
            )

        await set_file_identity(
            db,
            SIGMAHQ_ARCHIVE_IDENTITY_KEY,
            sha256=digest,
            commit_sha=commit_sha,
            synced_at=_utcnow_iso(),
            score_date=None,
        )
        await db.commit()
        return SyncResult(
            status="applied",
            commit_sha=commit_sha,
            archive_sha256=digest,
            stats=stats,
            message=f"Applied {stats.upserted} upserts, {stats.retired} retired",
        )
    finally:
        if tmp_ctx is not None:
            tmp_ctx.cleanup()


async def clear_sigmahq_identity(db: DbConnection) -> None:
    await clear_file_identity(db, SIGMAHQ_ARCHIVE_IDENTITY_KEY)


async def index_active_count(db: DbConnection) -> int:
    try:
        rows = await db.execute_fetchall(
            """
            SELECT COUNT(*) AS n FROM detection_rules
            WHERE source = $1 AND retired_at IS NULL
            """,
            (SOURCE,),
        )
        return int(rows[0]["n"]) if rows else 0
    except Exception:
        # Table missing on SQLite / pre-migration.
        return 0


async def find_index_rules_for_cve(
    db: DbConnection, cve_id: str, *, limit: int = 25
) -> list[dict[str, Any]]:
    """CVE-exact active rules from local index (Detect/Forge read path)."""
    cve = (cve_id or "").strip().upper()
    if not cve.startswith("CVE-"):
        return []
    try:
        rows = await db.execute_fetchall(
            """
            SELECT r.title, r.status, r.author, r.repo_path, r.content_yaml,
                   r.license_id, r.license_url, r.html_url, r.commit_sha,
                   c.match_basis
            FROM detection_rules r
            JOIN detection_rule_cves c ON c.rule_id = r.id
            WHERE c.cve_id = $1
              AND r.source = $2
              AND r.retired_at IS NULL
            ORDER BY r.title ASC
            LIMIT $3
            """,
            (cve, SOURCE, limit),
        )
    except Exception as exc:
        logger.debug("SigmaHQ index read skipped: %s", exc)
        return []

    out: list[dict[str, Any]] = []
    for row in rows:
        author = row.get("author") or ""
        html_url = row.get("html_url") or ""
        commit_sha = row.get("commit_sha") or ""
        path = row.get("repo_path") or ""
        download_url = ""
        if commit_sha and path:
            download_url = (
                f"https://raw.githubusercontent.com/{SIGMAHQ_REPO}/"
                f"{commit_sha}/{path}"
            )
        out.append(
            {
                "title": row.get("title") or path,
                "status": row.get("status") or "experimental",
                "source": "SigmaHQ",
                "path": path,
                "url": html_url,
                "html_url": html_url,
                "download_url": download_url,
                "content": row.get("content_yaml") or "",
                "author": author,
                "license": row.get("license_id") or LICENSE_ID,
                "license_url": row.get("license_url") or LICENSE_URL,
                "attribution": f"SigmaHQ · {author}" if author else "SigmaHQ",
                "match_basis": row.get("match_basis") or "cve_exact",
            }
        )
    return out
