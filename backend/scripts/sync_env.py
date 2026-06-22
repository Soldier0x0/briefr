#!/usr/bin/env python3
"""Sync .env with .env.example: keep existing values, add missing keys.

Walks .env.example line by line (preserving its comments/section grouping
and blank-line spacing) and regenerates .env, substituting in any value the
user already set. Keys present in .env but not in .env.example are appended
under a trailing "Custom / not in .env.example" section so nothing is lost.
"""
from __future__ import annotations

import argparse
import difflib
import re
import shutil
import sys
from pathlib import Path

KEY_LINE_RE = re.compile(r"^(?P<comment>#\s*)?(?P<key>[A-Za-z_][A-Za-z0-9_]*)=(?P<value>.*)$")


def parse_env_values(path: Path) -> dict[str, str]:
    """Return {KEY: value} for uncommented KEY=value lines."""
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        match = KEY_LINE_RE.match(line)
        if match and not match.group("comment"):
            values[match.group("key")] = match.group("value")
    return values


def build_synced_content(
    example_path: Path, env_values: dict[str, str]
) -> tuple[str, list[str], list[str]]:
    seen_keys: set[str] = set()
    out_lines: list[str] = []
    added_keys: list[str] = []

    for line in example_path.read_text(encoding="utf-8").splitlines():
        match = KEY_LINE_RE.match(line)
        if not match:
            out_lines.append(line)
            continue

        key = match.group("key")
        is_commented = bool(match.group("comment"))
        seen_keys.add(key)
        if key in env_values:
            out_lines.append(f"{key}={env_values[key]}")
        else:
            out_lines.append(line)
            if not is_commented:
                added_keys.append(key)

    orphans = {k: v for k, v in env_values.items() if k not in seen_keys}
    if orphans:
        out_lines.append("")
        out_lines.append("# --- Custom / not in .env.example ---")
        for key, value in orphans.items():
            out_lines.append(f"{key}={value}")

    return "\n".join(out_lines) + "\n", sorted(added_keys), sorted(orphans.keys())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    backend_dir = Path(__file__).resolve().parents[1]
    parser.add_argument("--example", type=Path, default=backend_dir / ".env.example")
    parser.add_argument("--env", type=Path, default=backend_dir / ".env")
    parser.add_argument("--dry-run", action="store_true", help="show a diff instead of writing")
    args = parser.parse_args()

    if not args.example.exists():
        print(f"error: {args.example} not found", file=sys.stderr)
        return 1

    existing_text = args.env.read_text(encoding="utf-8") if args.env.exists() else ""
    env_values = parse_env_values(args.env)
    new_text, new_keys, orphan_keys = build_synced_content(args.example, env_values)

    if args.dry_run:
        diff = difflib.unified_diff(
            existing_text.splitlines(keepends=True),
            new_text.splitlines(keepends=True),
            fromfile=str(args.env),
            tofile=f"{args.env} (synced)",
        )
        sys.stdout.writelines(diff)
        print(f"\n# keys to add: {len(new_keys)}, custom keys preserved: {len(orphan_keys)}")
        return 0

    if args.env.exists():
        backup_path = args.env.with_suffix(args.env.suffix + ".bak")
        shutil.copy2(args.env, backup_path)
        print(f"backed up {args.env} -> {backup_path}")

    args.env.write_text(new_text, encoding="utf-8")
    print(
        f"synced {args.env}: kept {len(env_values) - len(orphan_keys)}, "
        f"added {len(new_keys)}, custom (appended) {len(orphan_keys)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
