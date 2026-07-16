"""PM-3d: on-demand security architecture corpus drift check."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS = _REPO_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import generate_security_corpus as gen  # noqa: E402

_GENERATED_YAML = (
    "components.yaml",
    "api_inventory.yaml",
    "scheduler_jobs.yaml",
    "db_tables.yaml",
    "self_stack.yaml",
)


def check_corpus_drift() -> dict[str, Any]:
    """Regenerate the generated corpus layer and diff against committed files."""
    regenerated_dir = Path(tempfile.mkdtemp(prefix="briefr-corpus-drift-"))
    try:
        gen.generate(regenerated_dir)
        drifted: list[str] = []
        for filename in _GENERATED_YAML:
            committed = gen.CORPUS_DIR / filename
            fresh = regenerated_dir / filename
            with open(committed, encoding="utf-8") as f:
                committed_data = yaml.safe_load(f)
            with open(fresh, encoding="utf-8") as f:
                fresh_data = yaml.safe_load(f)
            if committed_data != fresh_data:
                drifted.append(filename)

        committed_graph = gen.CORPUS_DIR / "graphs" / "architecture.json"
        fresh_graph = regenerated_dir / "graphs" / "architecture.json"
        with open(committed_graph, encoding="utf-8") as f:
            committed_graph_data = json.load(f)
        with open(fresh_graph, encoding="utf-8") as f:
            fresh_graph_data = json.load(f)
        if committed_graph_data != fresh_graph_data:
            drifted.append("graphs/architecture.json")

        return {
            "ok": len(drifted) == 0,
            "drifted_files": drifted,
            "regenerate_command": "python scripts/generate_security_corpus.py",
        }
    finally:
        shutil.rmtree(regenerated_dir, ignore_errors=True)
