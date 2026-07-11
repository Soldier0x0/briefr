"""LLM artifact extraction for DetectionContext (Track K4).

Extracts structured ``{paths, params, keywords, method}`` artifacts from CVE
description text and exploit metadata. Scheduler-side only — never on the
request path. Uses the multi-provider LLM router (Groq → Gemini → OpenRouter).
"""

from __future__ import annotations

import json
import logging
import re

from ai.llm_router import LLMCompletion, chat_completion_task
from ai.llm_payload import has_substantive_source_text

logger = logging.getLogger(__name__)

MAX_ARTIFACTS_PER_CVE = 8
MAX_PATH_LEN = 200
MAX_PARAM_LEN = 80
MAX_KEYWORD_LEN = 80
MAX_METHOD_LEN = 16

NUCLEI_BLOB_PREFIX = "https://github.com/projectdiscovery/nuclei-templates/blob/main/"
NUCLEI_RAW_PREFIX = "https://raw.githubusercontent.com/projectdiscovery/nuclei-templates/main/"

SYSTEM_PROMPT = (
    "You are a detection engineer extracting HTTP attack surface details from "
    "vulnerability and exploit text. Respond with valid JSON only (no markdown fences)."
)

USER_PROMPT_TEMPLATE = """Extract detection-relevant HTTP artifacts from this CVE / exploit text.

Rules:
- paths: URL path patterns targeted by the vulnerability (e.g. "/api/login", "/admin/*")
- params: query or body parameter names mentioned as vulnerable
- keywords: response body or log keywords useful for hunting (short strings)
- method: HTTP method if clearly stated (GET, POST, etc.) — use "" if unknown
- Only include artifacts clearly supported by the text; do not invent paths
- Return an empty list if nothing concrete can be determined

Respond with JSON only:
{{"artifacts": [{{"paths": ["/..."], "params": ["..."], "keywords": ["..."], "method": "GET"}}]}}

CVE / exploit text:
{text}
"""


def _json_candidates(text: str):
    yield text
    fence = re.search(r"```(?:json)?\s*(.+?)\s*```", text, re.DOTALL | re.IGNORECASE)
    if fence:
        yield fence.group(1)
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        yield text[start : end + 1]


def _normalize_string_list(values: object, *, max_len: int, limit: int) -> list[str]:
    if not isinstance(values, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in values:
        token = str(item or "").strip()
        if not token:
            continue
        token = token[:max_len]
        key = token.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(token)
        if len(out) >= limit:
            break
    return out


def normalize_artifact(item: dict) -> dict | None:
    if not isinstance(item, dict):
        return None
    paths = _normalize_string_list(item.get("paths"), max_len=MAX_PATH_LEN, limit=5)
    params = _normalize_string_list(item.get("params"), max_len=MAX_PARAM_LEN, limit=10)
    keywords = _normalize_string_list(item.get("keywords"), max_len=MAX_KEYWORD_LEN, limit=10)
    method = str(item.get("method") or "").strip().upper()[:MAX_METHOD_LEN]
    if method not in ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", ""):
        method = ""
    if not paths and not params and not keywords:
        return None
    return {
        "paths": paths,
        "params": params,
        "keywords": keywords,
        "method": method,
    }


def parse_artifacts_payload(content: str) -> list[dict]:
    """Parse LLM JSON into validated artifact dicts. Never raises."""
    text = (content or "").strip()
    if not text:
        return []
    for candidate in _json_candidates(text):
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if (
            isinstance(data, dict)
            and "artifacts" not in data
            and ("paths" in data or "params" in data or "keywords" in data)
        ):
            items = [data]
        else:
            items = data.get("artifacts") if isinstance(data, dict) else data
        if not isinstance(items, list):
            continue
        artifacts: list[dict] = []
        for item in items:
            normalized = normalize_artifact(item) if isinstance(item, dict) else None
            if normalized:
                artifacts.append(normalized)
            if len(artifacts) >= MAX_ARTIFACTS_PER_CVE:
                break
        return artifacts
    return []


def nuclei_raw_url_from_blob(url: str) -> str | None:
    blob = (url or "").strip()
    if blob.startswith(NUCLEI_RAW_PREFIX) and blob.endswith(".yaml"):
        return blob
    if not blob.startswith(NUCLEI_BLOB_PREFIX):
        return None
    path = blob[len(NUCLEI_BLOB_PREFIX) :].strip("/")
    if not path.endswith(".yaml"):
        return None
    return f"{NUCLEI_RAW_PREFIX}{path}"


def format_exploit_lines(exploits: list[dict]) -> str:
    lines: list[str] = []
    for exp in exploits[:6]:
        source = str(exp.get("source") or "exploit").strip()
        title = str(exp.get("title") or "untitled").strip()
        url = str(exp.get("url") or "").strip()
        line = f"- [{source}] {title}"
        if url:
            line += f" ({url})"
        lines.append(line)
    return "\n".join(lines)


async def fetch_nuclei_template_text(url: str) -> str:
    """Fetch one Nuclei template YAML from GitHub raw (scheduler-side only)."""
    raw_url = nuclei_raw_url_from_blob(url)
    if not raw_url:
        return ""
    try:
        from resilient_client import resilient_get

        response = await resilient_get(
            "nuclei",
            raw_url,
            timeout=30.0,
            queue_operation="detection_rule_search",
            queue_context_type="task",
            queue_context_id="nuclei_template",
        )
        text = (response.text or "").strip()
        return text[:4000] if text else ""
    except Exception as exc:
        logger.warning("Nuclei template fetch failed for %s: %s", raw_url, exc)
        return ""


async def build_extraction_text(
    *,
    description: str,
    exploits: list[dict],
    include_nuclei_yaml: bool = True,
) -> str:
    parts: list[str] = []
    desc = (description or "").strip()
    if desc:
        parts.append(f"CVE description:\n{desc[:2500]}")
    exploit_block = format_exploit_lines(exploits)
    if exploit_block:
        parts.append(f"Known exploits:\n{exploit_block}")
    if include_nuclei_yaml:
        for exp in exploits:
            if str(exp.get("source") or "").lower() != "nuclei":
                continue
            yaml_text = await fetch_nuclei_template_text(str(exp.get("url") or ""))
            if yaml_text:
                parts.append(f"Nuclei template YAML:\n{yaml_text}")
                break
    return "\n\n".join(parts).strip()


async def extract_artifacts_via_llm(text: str) -> tuple[list[dict], LLMCompletion] | None:
    if not has_substantive_source_text(text):
        logger.info("Skipping LLM detection context extraction — empty source text")
        return None
    completion = await chat_completion_task(
        "detection_context",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": USER_PROMPT_TEMPLATE.format(text=text[:6000]),
            },
        ],
        max_tokens=700,
        temperature=0.0,
        timeout=60.0,
    )
    if not completion:
        return None
    return parse_artifacts_payload(completion.content), completion
