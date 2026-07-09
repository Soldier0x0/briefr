#!/usr/bin/env python3
"""Verify a BRIEFR intel snapshot bundle before import (Wave 4).

Usage:
  python scripts/verify_intel_snapshot.py briefr-intel-2026-07.pgdump.gz
  python scripts/verify_intel_snapshot.py --manifest briefr-intel.manifest.json
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
import tempfile
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "backend"))
sys.path.insert(0, str(_REPO / "scripts"))

from export_intel_snapshot import FORBIDDEN_TABLES, _verify_dump_tables  # noqa: E402
from snapshot_version import validate_format_version  # noqa: E402


def _load_manifest(bundle: Path | None, manifest_path: Path | None) -> dict:
    if manifest_path is not None:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    if bundle is None:
        raise ValueError("pass a bundle path or --manifest")
    sidecar = bundle.with_suffix(".manifest.json")
    if sidecar.is_file():
        return json.loads(sidecar.read_text(encoding="utf-8"))
    alt = bundle.parent / (bundle.name.replace(".pgdump.gz", "") + ".manifest.json")
    if alt.is_file():
        return json.loads(alt.read_text(encoding="utf-8"))
    raise FileNotFoundError(f"manifest not found for {bundle} (expected {sidecar})")


def verify_snapshot(
    bundle: Path | None,
    *,
    manifest_path: Path | None = None,
    skip_dump_catalog: bool = False,
) -> dict:
    manifest = _load_manifest(bundle, manifest_path)
    validate_format_version(manifest)

    if bundle is not None and bundle.is_file() and not skip_dump_catalog:
        if bundle.name.endswith(".gz"):
            with tempfile.NamedTemporaryFile(suffix=".pgdump", delete=False) as tmp:
                staging = Path(tmp.name)
            try:
                with gzip.open(bundle, "rb") as src, staging.open("wb") as dst:
                    dst.write(src.read())
                _verify_dump_tables(staging)
            finally:
                if staging.is_file():
                    staging.unlink()
        else:
            _verify_dump_tables(bundle)

    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify BRIEFR intel snapshot bundle")
    parser.add_argument("bundle", nargs="?", type=Path, help="Path to .pgdump.gz bundle")
    parser.add_argument("--manifest", type=Path, help="Manifest JSON path (skip bundle)")
    parser.add_argument(
        "--skip-dump-catalog",
        action="store_true",
        help="Validate manifest only (no pg_restore --list)",
    )
    args = parser.parse_args()
    if not args.bundle and not args.manifest:
        parser.error("pass bundle path or --manifest")
    try:
        manifest = verify_snapshot(
            args.bundle,
            manifest_path=args.manifest,
            skip_dump_catalog=args.skip_dump_catalog,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(manifest, indent=2))
    print("OK: snapshot verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
