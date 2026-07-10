"""Rule proof bench API (V1.5 Theme 2).

Copyright © 2026 Sai Harsha Vardhan
SPDX-License-Identifier: AGPL-3.0-or-later
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from proof.bench import run_proof

router = APIRouter()


class ProofRunRequest(BaseModel):
    lines: list[str] = Field(min_length=1, max_length=5000)
    sigma_yaml: str | None = Field(default=None, max_length=100_000)
    patterns: list[str] | None = Field(default=None, max_length=50)
    max_samples: int = Field(default=10, ge=1, le=50)


@router.post("/api/proof/run")
async def proof_run(body: ProofRunRequest):
    """Run a Sigma rule (or explicit patterns) against pasted log lines — file-based, no live SIEM."""
    if not body.sigma_yaml and not body.patterns:
        raise HTTPException(400, "Provide sigma_yaml or patterns")
    try:
        return run_proof(
            body.lines,
            sigma_yaml=body.sigma_yaml,
            patterns=body.patterns,
            max_samples=body.max_samples,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
