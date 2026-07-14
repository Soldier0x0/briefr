"""Design token lint gates (E0-1)."""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_design_token_lint_script_passes():
    proc = subprocess.run(
        [str(REPO_ROOT / "scripts" / "lint-design-tokens.sh")],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
