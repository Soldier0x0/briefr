"""Password hashing for built-in app login (decision 2026-06-11).

Plain `bcrypt` (not passlib — unmaintained, broken compat with bcrypt>=4.1).

Copyright © 2026 Sai Harsha Vardhan. All rights reserved.
"""

import bcrypt

# A fixed dummy hash so login can run verify_password() against *something*
# when no user matches the submitted email — keeps response timing roughly
# constant and avoids a timing oracle for user enumeration.
DUMMY_HASH = bcrypt.hashpw(b"not-a-real-password", bcrypt.gensalt(rounds=12)).decode("utf-8")


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False
