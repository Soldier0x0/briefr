"""Staging restore helpers for intel snapshot import."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from backup.postgres_util import _build_pg_cmd, _pg_tool, _subprocess_env, parse_postgres_url


def source_schema_from_manifest(manifest: dict) -> str:
    if manifest.get("format_version", 1) >= 2 and manifest.get("schema_split"):
        return "intel"
    return "public"


def remap_toc_for_staging(toc_text: str, source_schema: str, staging_schema: str) -> str:
    """Rewrite pg_restore TOC so objects land in ``staging_schema``."""
    if source_schema == staging_schema:
        return toc_text
    out: list[str] = []
    for line in toc_text.splitlines():
        if not line or line.startswith(";"):
            out.append(line)
            continue
        if f" {source_schema} " in line:
            line = line.replace(f" {source_schema} ", f" {staging_schema} ")
        elif line.rstrip().endswith(f" {source_schema};"):
            line = line[: line.rfind(f" {source_schema};")] + f" {staging_schema};"
        out.append(line)
    return "\n".join(out) + ("\n" if toc_text.endswith("\n") else "")


def restore_dump_to_schema(
    database_url: str,
    dump_path: Path,
    *,
    source_schema: str,
    target_schema: str,
) -> None:
    """Restore snapshot objects into ``target_schema`` (bootstrap replace)."""
    params = parse_postgres_url(database_url)
    list_proc = subprocess.run(
        [_pg_tool("pg_restore"), "--list", str(dump_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if list_proc.returncode != 0:
        detail = (list_proc.stderr or list_proc.stdout or "").strip()
        raise RuntimeError(f"pg_restore --list failed: {detail}")

    toc = remap_toc_for_staging(list_proc.stdout, source_schema, target_schema)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toc", delete=False) as handle:
        handle.write(toc)
        toc_path = Path(handle.name)

    restore_cmd = _build_pg_cmd(
        "pg_restore",
        params,
        extra_args=[
            "--no-owner",
            "--no-acl",
            "--data-only",
            "-L",
            str(toc_path),
            str(dump_path),
        ],
    )
    restore = subprocess.run(
        restore_cmd,
        env=_subprocess_env(params),
        capture_output=True,
        text=True,
        check=False,
    )
    toc_path.unlink(missing_ok=True)
    if restore.returncode not in {0, 1}:
        detail = (restore.stderr or restore.stdout or "").strip()
        raise RuntimeError(f"pg_restore to {target_schema} failed: {detail}")


def restore_dump_to_staging(
    database_url: str,
    dump_path: Path,
    *,
    source_schema: str,
    staging_schema: str = "intel_staging",
) -> None:
    """Load a snapshot dump into ``staging_schema`` without touching ``intel`` or ``app``."""
    params = parse_postgres_url(database_url)
    list_proc = subprocess.run(
        [_pg_tool("pg_restore"), "--list", str(dump_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if list_proc.returncode != 0:
        detail = (list_proc.stderr or list_proc.stdout or "").strip()
        raise RuntimeError(f"pg_restore --list failed: {detail}")

    toc = remap_toc_for_staging(list_proc.stdout, source_schema, staging_schema)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toc", delete=False) as handle:
        handle.write(toc)
        toc_path = Path(handle.name)

    prep_cmd = _build_pg_cmd(
        "psql",
        params,
        extra_args=[
            "-v",
            "ON_ERROR_STOP=1",
            "-c",
            f'DROP SCHEMA IF EXISTS "{staging_schema}" CASCADE;',
            "-c",
            f'CREATE SCHEMA "{staging_schema}";',
        ],
    )
    prep = subprocess.run(
        prep_cmd,
        env=_subprocess_env(params),
        capture_output=True,
        text=True,
        check=False,
    )
    if prep.returncode != 0:
        toc_path.unlink(missing_ok=True)
        detail = (prep.stderr or prep.stdout or "").strip()
        raise RuntimeError(f"failed to prepare staging schema: {detail}")

    restore_cmd = _build_pg_cmd(
        "pg_restore",
        params,
        extra_args=[
            "--no-owner",
            "--no-acl",
            "-L",
            str(toc_path),
            str(dump_path),
        ],
    )
    restore = subprocess.run(
        restore_cmd,
        env=_subprocess_env(params),
        capture_output=True,
        text=True,
        check=False,
    )
    toc_path.unlink(missing_ok=True)
    if restore.returncode not in {0, 1}:
        detail = (restore.stderr or restore.stdout or "").strip()
        raise RuntimeError(f"pg_restore to staging failed: {detail}")
