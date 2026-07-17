"""Regression tests for F7.1 — production must fail closed without JWT_SECRET.

The production guard has to run BEFORE the dev/test auto-generation block in
``settings.py``; otherwise auto-generation always populates ``jwt_secret`` and
the guard becomes dead code (the app silently mints a per-replica secret in
production). These run ``import settings`` in a subprocess with a controlled
environment and an empty cwd so ``load_dotenv()`` finds no stray ``.env``.
"""

import os
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _run_import(env_overrides, cwd):
    env = {
        k: v
        for k, v in os.environ.items()
        # Drop anything that could leak a secret / env into the child.
        if k not in {"JWT_SECRET", "BRIEFR_ENV"}
    }
    env["PYTHONPATH"] = str(BACKEND_DIR)
    env.update(env_overrides)
    return subprocess.run(
        [sys.executable, "-c", "import settings"],
        env=env,
        cwd=str(cwd),
        capture_output=True,
        text=True,
    )


def test_production_without_jwt_secret_fails_closed(tmp_path):
    result = _run_import({"BRIEFR_ENV": "production"}, cwd=tmp_path)
    assert result.returncode != 0, (
        "production import must fail without JWT_SECRET; "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert "JWT_SECRET must be set in production" in result.stderr


def test_production_with_jwt_secret_boots(tmp_path):
    result = _run_import(
        {"BRIEFR_ENV": "production", "JWT_SECRET": "0" * 64},
        cwd=tmp_path,
    )
    assert result.returncode == 0, (
        f"production import should succeed with JWT_SECRET; stderr={result.stderr!r}"
    )
