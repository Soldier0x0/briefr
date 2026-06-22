"""Username validation for built-in app login.

Usernames are normalized to lowercase on storage and lookup. Rules are
intentionally strict to reduce homograph confusion and keep audit logs readable.

Copyright © 2026 Sai Harsha Vardhan. All rights reserved.
"""

from __future__ import annotations

import re

USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,30}[a-z0-9]$")
USERNAME_MIN_LEN = 3
USERNAME_MAX_LEN = 32


def normalize_username(raw: str) -> str:
    return raw.strip().lower()


def validate_username(raw: str) -> str:
    """Return normalized username or raise ValueError with a safe message."""
    username = normalize_username(raw)
    if len(username) < USERNAME_MIN_LEN or len(username) > USERNAME_MAX_LEN:
        raise ValueError(
            f"Username must be {USERNAME_MIN_LEN}–{USERNAME_MAX_LEN} characters."
        )
    if not USERNAME_RE.match(username):
        raise ValueError(
            "Username may only contain letters, numbers, underscores, and hyphens, "
            "and must start and end with a letter or number."
        )
    return username


def is_valid_username(raw: str) -> bool:
    try:
        validate_username(raw)
        return True
    except ValueError:
        return False
