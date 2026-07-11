"""Load and validate the Security Architecture Corpus (SAC).

Copyright © 2026 Sai Harsha Vardhan
SPDX-License-Identifier: AGPL-3.0-or-later
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

CORPUS_DIR = Path(__file__).resolve().parent / "corpus"

_REQUIRED_ENTITY_FIELDS = ("id", "title", "summary")
_REQUIRED_MANIFEST_FIELDS = ("version", "schema_version", "title", "sections")


@dataclass
class SecurityArchitectureCorpus:
    manifest: dict[str, Any]
    components: list[dict[str, Any]] = field(default_factory=list)
    trust_boundaries: list[dict[str, Any]] = field(default_factory=list)
    controls: list[dict[str, Any]] = field(default_factory=list)
    abuse_cases: list[dict[str, Any]] = field(default_factory=list)
    threat_scenarios: list[dict[str, Any]] = field(default_factory=list)
    security_decisions: list[dict[str, Any]] = field(default_factory=list)
    risks: list[dict[str, Any]] = field(default_factory=list)
    reviews: list[dict[str, Any]] = field(default_factory=list)
    stride: list[dict[str, Any]] = field(default_factory=list)
    owasp_top10: list[dict[str, Any]] = field(default_factory=list)
    owasp_api: list[dict[str, Any]] = field(default_factory=list)
    nist_csf: list[dict[str, Any]] = field(default_factory=list)
    asvs: list[dict[str, Any]] = field(default_factory=list)
    capec_mappings: list[dict[str, Any]] = field(default_factory=list)
    architecture_graph: dict[str, Any] = field(default_factory=dict)
    attack_surface_graph: dict[str, Any] = field(default_factory=dict)

    def entity_index(self) -> dict[str, dict[str, Any]]:
        """Flat id → record map for search/context (corpus entities only)."""
        index: dict[str, dict[str, Any]] = {}
        for collection, entity_type in (
            (self.components, "component"),
            (self.trust_boundaries, "trust_boundary"),
            (self.controls, "control"),
            (self.abuse_cases, "abuse_case"),
            (self.threat_scenarios, "threat_scenario"),
            (self.security_decisions, "security_decision"),
            (self.risks, "risk"),
            (self.reviews, "review"),
        ):
            for row in collection:
                index[row["id"]] = {**row, "_entity_type": entity_type}
        return index


_corpus_cache: SecurityArchitectureCorpus | None = None
_corpus_mtime: float = 0.0


def _load_yaml(path: Path) -> Any:
    if not path.is_file():
        raise FileNotFoundError(f"Missing corpus file: {path}")
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _load_json(path: Path) -> dict[str, Any]:
    import json

    if not path.is_file():
        raise FileNotFoundError(f"Missing corpus file: {path}")
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"{path.name} must be a JSON object")
    return data


def _validate_entities(label: str, rows: list[Any]) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        raise ValueError(f"{label} must be a list")
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for raw in rows:
        if not isinstance(raw, dict):
            raise ValueError(f"{label} entries must be objects")
        row = dict(raw)
        if not row.get("summary") and row.get("purpose"):
            row["summary"] = row["purpose"]
        if not row.get("summary") and row.get("description"):
            row["summary"] = row["description"]
        for key in _REQUIRED_ENTITY_FIELDS:
            if not row.get(key):
                raise ValueError(f"{label} entry missing {key}: {row.get('id')}")
        eid = str(row["id"])
        if eid in seen:
            raise ValueError(f"Duplicate {label} id: {eid}")
        seen.add(eid)
        out.append(row)
    return out


def _validate_manifest(manifest: Any) -> dict[str, Any]:
    if not isinstance(manifest, dict):
        raise ValueError("manifest.yaml must be a mapping")
    for key in _REQUIRED_MANIFEST_FIELDS:
        if key not in manifest:
            raise ValueError(f"manifest.yaml missing required field: {key}")
    sections = manifest.get("sections")
    if not isinstance(sections, list) or not sections:
        raise ValueError("manifest.sections must be a non-empty list")
    return manifest


def load_corpus(*, corpus_dir: Path | None = None) -> SecurityArchitectureCorpus:
    """Load and validate the full Security Architecture Corpus from disk."""
    root = corpus_dir or CORPUS_DIR
    manifest = _validate_manifest(_load_yaml(root / "manifest.yaml"))

    components_raw = _load_yaml(root / "components.yaml")
    controls_raw = _load_yaml(root / "controls.yaml")

    corpus = SecurityArchitectureCorpus(
        manifest=manifest,
        components=_validate_entities("components", components_raw.get("components", [])),
        trust_boundaries=_validate_entities(
            "trust_boundaries", _load_yaml(root / "trust_boundaries.yaml").get("trust_boundaries", [])
        ),
        controls=_validate_entities("controls", controls_raw.get("controls", [])),
        abuse_cases=_validate_entities(
            "abuse_cases", _load_yaml(root / "abuse_cases.yaml").get("abuse_cases", [])
        ),
        threat_scenarios=_validate_entities(
            "threat_scenarios", _load_yaml(root / "threat_scenarios.yaml").get("scenarios", [])
        ),
        security_decisions=_validate_entities(
            "security_decisions",
            _load_yaml(root / "security_decisions.yaml").get("decisions", []),
        ),
        risks=_validate_entities("risks", _load_yaml(root / "risks.yaml").get("risks", [])),
        reviews=_validate_entities("reviews", _load_yaml(root / "reviews.yaml").get("reviews", [])),
        stride=_validate_entities(
            "stride", _load_yaml(root / "frameworks" / "stride.yaml").get("matrices", [])
        ),
        owasp_top10=_validate_entities(
            "owasp_top10", _load_yaml(root / "frameworks" / "owasp_top10.yaml").get("categories", [])
        ),
        owasp_api=_validate_entities(
            "owasp_api", _load_yaml(root / "frameworks" / "owasp_api.yaml").get("categories", [])
        ),
        nist_csf=_validate_entities(
            "nist_csf", _load_yaml(root / "frameworks" / "nist_csf.yaml").get("functions", [])
        ),
        asvs=_validate_entities(
            "asvs", _load_yaml(root / "frameworks" / "asvs.yaml").get("chapters", [])
        ),
        capec_mappings=_validate_entities(
            "capec_mappings",
            _load_yaml(root / "frameworks" / "capec_mappings.yaml").get("patterns", []),
        ),
        architecture_graph=_load_json(root / "graphs" / "architecture.json"),
        attack_surface_graph=_load_json(root / "graphs" / "attack_surface.json"),
    )
    return corpus


def _corpus_fingerprint(corpus_dir: Path) -> float:
    latest = 0.0
    if not corpus_dir.is_dir():
        return latest
    for path in corpus_dir.rglob("*"):
        if path.is_file():
            latest = max(latest, path.stat().st_mtime)
    return latest


def get_corpus() -> SecurityArchitectureCorpus:
    """Return cached corpus; reload when any corpus file changes."""
    global _corpus_cache, _corpus_mtime
    mtime = _corpus_fingerprint(CORPUS_DIR)
    if _corpus_cache is None or mtime > _corpus_mtime:
        _corpus_cache = load_corpus()
        _corpus_mtime = mtime
    return _corpus_cache


def reload_corpus() -> SecurityArchitectureCorpus:
    """Force reload (tests)."""
    global _corpus_cache, _corpus_mtime
    _corpus_cache = load_corpus()
    _corpus_mtime = _corpus_fingerprint(CORPUS_DIR)
    return _corpus_cache
