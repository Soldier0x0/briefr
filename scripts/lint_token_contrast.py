#!/usr/bin/env python3
"""Validate key text-on-surface pairs from tokens.css meet WCAG 2.1 AA."""

from __future__ import annotations

import re
import sys
from pathlib import Path

TOKENS_PATH = Path(__file__).resolve().parents[1] / "frontend/src/styles/tokens.css"

DARK_PAIRS = [
    ("--text-primary", "--background-primary", 4.5),
    ("--text-secondary", "--background-primary", 4.5),
    ("--text-muted", "--background-primary", 4.5),
    ("--text-heading", "--background-primary", 4.5),
    ("--text-disabled", "--background-primary", 3.0),
    ("--severity-critical", "--background-primary", 3.0),
    ("--status-error", "--background-primary", 3.0),
]

LIGHT_PAIRS = [
    ("--text-primary", "--background-primary", 4.5),
    ("--text-secondary", "--background-primary", 4.5),
    ("--text-muted", "--background-primary", 4.5),
    ("--severity-critical", "--background-primary", 3.0),
    ("--status-error", "--background-primary", 3.0),
]


def strip_comment(value: str) -> str:
    return re.sub(r"/\*.*?\*/", "", value).strip()


def parse_hex(value: str) -> tuple[float, float, float] | None:
    value = strip_comment(value).rstrip(";").strip()
    m = re.fullmatch(r"#([0-9a-fA-F]{6})", value)
    if not m:
        return None
    h = m.group(1)
    return (
        int(h[0:2], 16) / 255,
        int(h[2:4], 16) / 255,
        int(h[4:6], 16) / 255,
    )


def linearize(c: float) -> float:
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def luminance(rgb: tuple[float, float, float]) -> float:
    r, g, b = (linearize(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(fg: tuple[float, float, float], bg: tuple[float, float, float]) -> float:
    l1, l2 = luminance(fg), luminance(bg)
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def extract_vars(css: str, selector: str) -> dict[str, str]:
    pattern = re.escape(selector) + r"\s*\{([^}]*)\}"
    m = re.search(pattern, css, re.DOTALL)
    if not m:
        return {}
    out: dict[str, str] = {}
    for raw_line in m.group(1).splitlines():
        line = strip_comment(raw_line.strip())
        for part in line.split(";"):
            part = part.strip()
            if not part or ":" not in part:
                continue
            name, val = part.split(":", 1)
            out[name.strip()] = val.strip()
    return out


def extract_all_root_blocks(css: str) -> list[dict[str, str]]:
    blocks: list[dict[str, str]] = []
    for m in re.finditer(r":root(?:\[[^\]]+\])?\s*\{", css):
        start = m.end()
        depth = 1
        i = start
        while i < len(css) and depth:
            if css[i] == "{":
                depth += 1
            elif css[i] == "}":
                depth -= 1
            i += 1
        body = css[start : i - 1]
        block: dict[str, str] = {}
        for raw_line in body.splitlines():
            line = strip_comment(raw_line.strip())
            for part in line.split(";"):
                part = part.strip()
                if not part or ":" not in part:
                    continue
                name, val = part.split(":", 1)
                block[name.strip()] = val.strip()
        blocks.append(block)
    return blocks


def resolve(var_name: str, scope: dict[str, str]) -> str | None:
    seen: set[str] = set()
    current = var_name
    while current in scope and current not in seen:
        seen.add(current)
        val = strip_comment(scope[current])
        if val.startswith("#"):
            return val
        if val.startswith("var("):
            inner = val[4:-1].strip()
            current = inner.split(",")[0].strip()
            continue
        return None
    return None


def main() -> int:
    css = TOKENS_PATH.read_text(encoding="utf-8")
    blocks = extract_all_root_blocks(css)
    if len(blocks) < 2:
        print("Could not parse tokens.css :root blocks", file=sys.stderr)
        return 1

    primitives = blocks[0]
    dark = {**primitives, **blocks[1]}
    light_override = extract_vars(css, ':root[data-theme="light"]')
    light = {**dark, **light_override}

    errors: list[str] = []

    for fg, bg, min_ratio in DARK_PAIRS:
        fg_hex = resolve(fg, dark)
        bg_hex = resolve(bg, dark)
        if not fg_hex or not bg_hex:
            errors.append(f"dark: unresolved {fg} on {bg}")
            continue
        fg_rgb, bg_rgb = parse_hex(fg_hex), parse_hex(bg_hex)
        if not fg_rgb or not bg_rgb:
            errors.append(f"dark: non-hex {fg}={fg_hex} {bg}={bg_hex}")
            continue
        ratio = contrast_ratio(fg_rgb, bg_rgb)
        if ratio < min_ratio:
            errors.append(f"dark: {fg} on {bg} = {ratio:.2f}:1 (need {min_ratio})")

    for fg, bg, min_ratio in LIGHT_PAIRS:
        fg_hex = resolve(fg, light)
        bg_hex = resolve(bg, light)
        if not fg_hex or not bg_hex:
            errors.append(f"light: unresolved {fg} on {bg}")
            continue
        fg_rgb, bg_rgb = parse_hex(fg_hex), parse_hex(bg_hex)
        if not fg_rgb or not bg_rgb:
            errors.append(f"light: non-hex {fg}={fg_hex} {bg}={bg_hex}")
            continue
        ratio = contrast_ratio(fg_rgb, bg_rgb)
        if ratio < min_ratio:
            errors.append(f"light: {fg} on {bg} = {ratio:.2f}:1 (need {min_ratio})")

    if errors:
        for e in errors:
            print(e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
