"""Deterministic Nuclei template YAML parser (Sprint D4).

Extracts ``{paths, params, keywords, method}`` artifacts from Nuclei HTTP
blocks without an LLM. Scheduler-side only.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qs, urlparse

import yaml

from detection.artifact_extract import MAX_ARTIFACTS_PER_CVE, normalize_artifact

_TEMPLATE_VAR_RE = re.compile(r"\{\{[^}]+\}\}")
_RAW_REQUEST_LINE_RE = re.compile(
    r"^(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s+(\S+)",
    re.IGNORECASE | re.MULTILINE,
)


def _strip_template_vars(value: str) -> str:
    cleaned = _TEMPLATE_VAR_RE.sub("", value or "").strip()
    return cleaned


def _normalize_path(raw: str) -> str:
    path = _strip_template_vars(raw).strip()
    if not path:
        return ""
    if path.startswith("http://") or path.startswith("https://"):
        parsed = urlparse(path)
        path = parsed.path or "/"
    if not path.startswith("/"):
        if "?" in path:
            path = "/" + path.lstrip("/")
        elif path and not path.startswith("/"):
            path = f"/{path}"
    # Drop query for path list; params extracted separately.
    if "?" in path:
        path = path.split("?", 1)[0]
    return path[:200]


def _query_params_from_path(raw: str) -> list[str]:
    token = _strip_template_vars(raw)
    if "?" not in token:
        return []
    query = token.split("?", 1)[1]
    parsed = parse_qs(query, keep_blank_values=False)
    return [key for key in parsed if key][:10]


def _matcher_words(matchers: Any) -> list[str]:
    if not isinstance(matchers, list):
        return []
    words: list[str] = []
    for matcher in matchers:
        if not isinstance(matcher, dict):
            continue
        if matcher.get("type") not in ("word", "regex"):
            continue
        raw_words = matcher.get("words") or matcher.get("regex") or []
        if isinstance(raw_words, str):
            raw_words = [raw_words]
        if not isinstance(raw_words, list):
            continue
        for word in raw_words:
            token = str(word or "").strip()
            if not token or token in ("dns",):
                continue
            if len(token) > 80:
                token = token[:80]
            words.append(token)
    return words


def _parse_raw_block(raw: Any) -> tuple[str, list[str], list[str]]:
    if raw is None:
        return "", [], []
    if isinstance(raw, str):
        blocks = [raw]
    elif isinstance(raw, list):
        blocks = [str(item) for item in raw if item]
    else:
        return "", [], []

    method = ""
    paths: list[str] = []
    params: list[str] = []
    for block in blocks:
        for match in _RAW_REQUEST_LINE_RE.finditer(block):
            if not method:
                method = match.group(1).upper()
            path_token = match.group(2)
            normalized = _normalize_path(path_token)
            if normalized:
                paths.append(normalized)
            params.extend(_query_params_from_path(path_token))
    return method, paths, params


def _parse_http_entry(entry: dict) -> dict | None:
    if not isinstance(entry, dict):
        return None

    method = str(entry.get("method") or "").strip().upper()
    paths: list[str] = []
    params: list[str] = []
    keywords = _matcher_words(entry.get("matchers"))

    raw_method, raw_paths, raw_params = _parse_raw_block(entry.get("raw"))
    if not method and raw_method:
        method = raw_method
    paths.extend(raw_paths)
    params.extend(raw_params)

    for raw_path in entry.get("path") or []:
        token = str(raw_path or "")
        normalized = _normalize_path(token)
        if normalized:
            paths.append(normalized)
        params.extend(_query_params_from_path(token))

    return normalize_artifact(
        {
            "paths": paths,
            "params": params,
            "keywords": keywords,
            "method": method,
        }
    )


def parse_nuclei_template_yaml(yaml_text: str) -> list[dict]:
    """Parse Nuclei template YAML into normalized artifact dicts."""
    text = (yaml_text or "").strip()
    if not text:
        return []
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError:
        return []
    if not isinstance(data, dict):
        return []

    artifacts: list[dict] = []
    http_blocks = data.get("http")
    if not isinstance(http_blocks, list):
        return []

    for entry in http_blocks:
        if not isinstance(entry, dict):
            continue
        parsed = _parse_http_entry(entry)
        if parsed:
            artifacts.append(parsed)
        if len(artifacts) >= MAX_ARTIFACTS_PER_CVE:
            break

    return artifacts[:MAX_ARTIFACTS_PER_CVE]
