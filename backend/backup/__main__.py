"""CLI: python -m backup [run|list|restore|verify]"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from backup.manager import (
    BackupConfig,
    check_db_integrity,
    ensure_db_or_restore,
    find_latest_valid_backup,
    list_backups,
    restore_backup,
    run_backup,
)


def _cmd_run(args: argparse.Namespace) -> int:
    result = run_backup(reason=args.reason)
    print(json.dumps(result, indent=2))
    return 0 if result.get("status") == "ok" else 1


def _cmd_list(_: argparse.Namespace) -> int:
    rows = list_backups()
    print(json.dumps(rows, indent=2))
    return 0


def _cmd_restore(args: argparse.Namespace) -> int:
    cfg = BackupConfig.from_env()
    archive = Path(args.archive) if args.archive else find_latest_valid_backup(cfg)
    if not archive:
        print("No valid backup archive found", file=sys.stderr)
        return 1
    result = restore_backup(archive, config=cfg, force=args.force)
    print(json.dumps(result, indent=2))
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    cfg = BackupConfig.from_env()
    target = Path(args.path) if args.path else cfg.db_path
    ok, msg = check_db_integrity(target)
    print(json.dumps({"path": str(target), "ok": ok, "integrity": msg}, indent=2))
    return 0 if ok else 1


def _cmd_ensure(_: argparse.Namespace) -> int:
    result = ensure_db_or_restore()
    print(json.dumps(result, indent=2))
    return 0 if result.get("status") in {"healthy", "no_db", "restored", "skipped"} else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="BRIEFR backup manager")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Create a new backup archive")
    run_p.add_argument(
        "--reason",
        default="manual",
        help="Label stored in manifest (scheduled, pre-update, manual, ...)",
    )
    run_p.set_defaults(func=_cmd_run)

    sub.add_parser("list", help="List backup archives newest-first").set_defaults(
        func=_cmd_list
    )

    restore_p = sub.add_parser("restore", help="Restore database from archive")
    restore_p.add_argument(
        "archive",
        nargs="?",
        help="Path to briefr-*.tar.gz (default: newest valid)",
    )
    restore_p.add_argument(
        "--force",
        action="store_true",
        help="Overwrite even when the live database passes integrity_check",
    )
    restore_p.set_defaults(func=_cmd_restore)

    verify_p = sub.add_parser("verify", help="Run PRAGMA integrity_check on a DB file")
    verify_p.add_argument("path", nargs="?", help="Database path (default: live DB_PATH)")
    verify_p.set_defaults(func=_cmd_verify)

    sub.add_parser(
        "ensure",
        help="Verify live DB; restore from latest valid backup if corrupt",
    ).set_defaults(func=_cmd_ensure)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
