"""Password hashing for built-in app login (decision 2026-06-11).

Plain `bcrypt` (not passlib — unmaintained, broken compat with bcrypt>=4.1).

Copyright © 2026 Sai Harsha Vardhan
SPDX-License-Identifier: Apache-2.0
"""

import secrets

import bcrypt

# A dummy hash so login can run verify_password() against *something* when no
# user matches the submitted username — keeps response timing roughly constant
# and avoids a timing oracle for user enumeration. Randomized at import time
# so no caller could ever construct a plaintext that verifies against it.
DUMMY_HASH = bcrypt.hashpw(secrets.token_bytes(32), bcrypt.gensalt(rounds=12)).decode("utf-8")


PASSWORD_MAX_LEN = 128


def validate_password_strength(password: str) -> None:
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters.")
    if len(password) > PASSWORD_MAX_LEN:
        raise ValueError(f"Password must be at most {PASSWORD_MAX_LEN} characters.")


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False
