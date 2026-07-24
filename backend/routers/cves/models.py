"""CVE router package.

Split from `routers.cves` (F1.2) without changing route registration order or
handler behavior.

Copyright © 2026 Sai Harsha Vardhan
SPDX-License-Identifier: Apache-2.0
"""

from pydantic import BaseModel, Field


class AssetMatchItem(BaseModel):
    product: str = Field(..., max_length=200)
    version: str = Field(default="", max_length=100)
    vendor: str = Field(default="", max_length=100)


class AssetMatchRequest(BaseModel):
    assets: list[AssetMatchItem] = Field(default_factory=list, max_length=500)


class RiskScoreRequest(BaseModel):
    """Optional asset profile for personalised Risk Score / ADR-002 OP.

    ``profile`` may include W5 exposure fields (OP/SSVC only, never Threat):
    ``internet_facing`` (bool), ``criticality``
    (``MISSION_CRITICAL``|``IMPORTANT``|``SUPPORTING``), and optional
    ``privileged_service`` / ``ot_safety`` (bool). Absent flags preserve
    pre-W5 behaviour.
    """

    profile: dict | None = None
    assets: list[AssetMatchItem] = Field(default_factory=list, max_length=500)


class CorrelationSuppressBody(BaseModel):
    scope: str = Field(
        description="campaign_id | cve_pair | pulse_id | infrastructure"
    )
    key: dict = Field(default_factory=dict)
    reason: str = ""
    dismissed_by: str = Field(
        default="",
        description="Analyst identity, free-text until app login ships",
    )


class CorrelationFeedbackBody(BaseModel):
    scope: str = Field(
        description="campaign_id | cve_pair | pulse_id | infrastructure"
    )
    key: dict = Field(default_factory=dict)
    verdict: str = Field(description="confirm | reject | resolve_conflict")
    reason: str = ""
    created_by: str = Field(
        default="",
        description="Analyst identity, free-text until app login ships",
    )
