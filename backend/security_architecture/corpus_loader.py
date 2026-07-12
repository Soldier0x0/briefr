"""TM-1: load + validate the Security Architecture Corpus (SAC).

Schema rules (spec §4.1): every entity has id/title/summary/status/owner/
origin; curated entities additionally carry review_date/evidence[]/
related_ids[]. `related_ids[]` must resolve to real ids elsewhere in the
corpus -- a dangling reference is a validation error, not a warning, so the
corpus can't silently rot into referencing deleted entities.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

CORPUS_DIR = Path(__file__).resolve().parent / "corpus"

_VALID_ORIGINS = frozenset({"generated", "curated"})

# file -> (top-level list key, whether every record needs review_date/evidence)
_GENERATED_FILES: dict[str, str] = {
    "components.yaml": "components",
    "api_inventory.yaml": "endpoints",
    "scheduler_jobs.yaml": "jobs",
    "db_tables.yaml": "tables",
}
_CURATED_FILES: dict[str, str] = {
    "trust_boundaries.yaml": "trust_boundaries",
    "controls.yaml": "controls",
    "abuse_cases.yaml": "abuse_cases",
    "threat_scenarios.yaml": "threat_scenarios",
    "security_decisions.yaml": "security_decisions",
    "risks.yaml": "risks",
    "reviews.yaml": "reviews",
}

# api_inventory entries are endpoints, not standalone corpus entities --
# they don't carry id/title/summary, just method/path/component_id.
_NO_ID_REQUIRED = frozenset({"api_inventory.yaml"})


class CorpusValidationError(ValueError):
    """A corpus file failed schema validation."""


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        raise CorpusValidationError(f"{path.name}: invalid YAML ({exc})") from exc
    if not isinstance(data, dict):
        raise CorpusValidationError(f"{path.name}: root must be a mapping")
    return data


def _validate_record(filename: str, record: dict[str, Any], all_ids: set[str]) -> None:
    if not isinstance(record, dict):
        raise CorpusValidationError(f"{filename}: record is not a mapping: {record!r}")

    if filename not in _NO_ID_REQUIRED:
        for field in ("id", "title", "summary", "origin"):
            if not record.get(field):
                raise CorpusValidationError(
                    f"{filename}: record missing required field '{field}': {record!r}"
                )
        origin = record["origin"]
        if origin not in _VALID_ORIGINS:
            raise CorpusValidationError(
                f"{filename}: record '{record.get('id')}' has invalid origin '{origin}' "
                f"(must be one of {sorted(_VALID_ORIGINS)})"
            )
        if origin == "curated":
            for field in ("review_date", "evidence", "related_ids"):
                if field not in record:
                    raise CorpusValidationError(
                        f"{filename}: curated record '{record['id']}' missing "
                        f"required field '{field}'"
                    )

    for rid in record.get("related_ids") or []:
        if rid not in all_ids:
            raise CorpusValidationError(
                f"{filename}: record '{record.get('id')}' references unknown "
                f"related_ids entry '{rid}'"
            )


def load_corpus(corpus_dir: Path | None = None) -> dict[str, Any]:
    """Load and validate every corpus file. Returns {file_stem: parsed_data}.

    Raises CorpusValidationError on any schema violation -- callers (the
    router, tests) should let this surface as a hard failure rather than
    silently serving a partial/broken corpus.
    """
    directory = corpus_dir or CORPUS_DIR
    all_files = {**_GENERATED_FILES, **_CURATED_FILES}

    manifest_path = directory / "manifest.yaml"
    if not manifest_path.exists():
        raise CorpusValidationError("Missing corpus file: manifest.yaml")
    manifest = _load_yaml(manifest_path)
    for field in ("version", "schema_version", "last_reviewed"):
        if field not in manifest:
            raise CorpusValidationError(f"manifest.yaml: missing required field '{field}'")

    raw: dict[str, dict[str, Any]] = {}
    for filename in all_files:
        path = directory / filename
        if not path.exists():
            raise CorpusValidationError(f"Missing corpus file: {filename}")
        raw[filename] = _load_yaml(path)

    # Collect every id across every file before validating related_ids, so
    # a control referencing a component (cross-file) resolves correctly.
    all_ids: set[str] = set()
    for filename, list_key in all_files.items():
        if filename in _NO_ID_REQUIRED:
            continue
        for record in raw[filename].get(list_key) or []:
            if isinstance(record, dict) and record.get("id"):
                all_ids.add(record["id"])

    for filename, list_key in all_files.items():
        for record in raw[filename].get(list_key) or []:
            _validate_record(filename, record, all_ids)

    result = {Path(filename).stem: data for filename, data in raw.items()}
    result["manifest"] = manifest
    return result


_cache: dict[str, Any] | None = None
_cache_mtime: float | None = None


def get_corpus(corpus_dir: Path | None = None) -> dict[str, Any]:
    """Cached load, invalidated when any corpus file's mtime changes."""
    global _cache, _cache_mtime

    directory = corpus_dir or CORPUS_DIR
    all_files = {**_GENERATED_FILES, **_CURATED_FILES, "manifest.yaml": None}
    latest_mtime = max(
        (directory / filename).stat().st_mtime
        for filename in all_files
        if (directory / filename).exists()
    )

    if _cache is None or _cache_mtime != latest_mtime:
        _cache = load_corpus(directory)
        _cache_mtime = latest_mtime

    return _cache
