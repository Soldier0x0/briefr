"""File-based rule proof bench (V1.5 Theme 2).

Copyright © 2026 Sai Harsha Vardhan
SPDX-License-Identifier: BUSL-1.1
"""

from __future__ import annotations

from typing import Any

import yaml


def _collect_strings(obj: Any, out: list[str]) -> None:
    if isinstance(obj, str):
        text = obj.strip()
        if len(text) >= 3:
            out.append(text)
    elif isinstance(obj, list):
        for item in obj:
            _collect_strings(item, out)
    elif isinstance(obj, dict):
        for value in obj.values():
            _collect_strings(value, out)


def extract_patterns_from_sigma(sigma_yaml: str) -> tuple[list[str], list[str]]:
    """Return (match_patterns, false_positive_hints) from Sigma YAML."""
    data = yaml.safe_load(sigma_yaml) or {}
    detection = data.get("detection") or {}
    patterns: list[str] = []
    _collect_strings(detection.get("keywords"), patterns)
    _collect_strings(detection.get("selection"), patterns)
    _collect_strings(detection.get("selection_*"), patterns)
    for key, value in detection.items():
        if key.startswith("selection"):
            _collect_strings(value, patterns)
    # Dedupe while preserving order; drop overly generic tokens
    seen: set[str] = set()
    unique: list[str] = []
    for p in patterns:
        norm = p.lower()
        if norm in seen or len(norm) < 3:
            continue
        seen.add(norm)
        unique.append(p)
    false_positives = [str(x) for x in (data.get("falsepositives") or []) if str(x).strip()]
    return unique[:40], false_positives


def _line_matches(line: str, pattern: str) -> bool:
    lower_line = line.lower()
    pat = pattern.lower()
    if "|endswith" in pattern:
        # Not in collected strings — raw yaml keys skipped
        return False
    if pat.startswith("r\\") or pat.startswith("\\"):
        suffix = pat.lstrip("r").strip("\\")
        return lower_line.endswith(suffix.lower())
    return pat in lower_line


def run_proof(
    lines: list[str],
    *,
    sigma_yaml: str | None = None,
    patterns: list[str] | None = None,
    max_samples: int = 10,
) -> dict[str, Any]:
    """Match log lines against Sigma keywords/selection strings or explicit patterns."""
    if sigma_yaml:
        extracted, false_positives = extract_patterns_from_sigma(sigma_yaml)
        use_patterns = extracted
    else:
        use_patterns = [p for p in (patterns or []) if p and p.strip()]
        false_positives = []

    if not use_patterns:
        raise ValueError("no match patterns — provide sigma_yaml or patterns")

    hits: list[dict[str, Any]] = []
    for idx, raw in enumerate(lines, start=1):
        line = raw.rstrip("\n")
        if not line.strip():
            continue
        matched = [p for p in use_patterns if _line_matches(line, p)]
        if matched:
            hits.append({"line_number": idx, "line": line[:500], "matched_patterns": matched[:5]})
        if len(hits) >= max_samples:
            break

    non_empty = sum(1 for raw in lines if raw.strip())
    hit_count = 0
    for idx, raw in enumerate(lines, start=1):
        line = raw.rstrip("\n")
        if not line.strip():
            continue
        if any(_line_matches(line, p) for p in use_patterns):
            hit_count += 1

    miss_count = max(non_empty - hit_count, 0)
    return {
        "total_lines": non_empty,
        "hit_count": hit_count,
        "miss_count": miss_count,
        "hit_rate": round(hit_count / non_empty, 4) if non_empty else 0.0,
        "patterns": use_patterns,
        "false_positive_hints": false_positives,
        "sample_hits": hits,
    }
