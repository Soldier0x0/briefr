"""Shared GitHub API helpers for repo-based intel feeds."""

from __future__ import annotations

import os

GITHUB_API = "https://api.github.com"
GITHUB_RAW = "https://raw.githubusercontent.com"


def github_headers() -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def raw_repo_url(owner: str, repo: str, branch: str, path: str) -> str:
    return f"{GITHUB_RAW}/{owner}/{repo}/{branch}/{path}"
