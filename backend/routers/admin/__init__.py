"""Admin dashboard API — package aggregate.

Part of the `routers.admin` package (F1.2 / W7 split). Aggregate router is
re-exported from `routers.admin`.

Copyright © 2026 Sai Harsha Vardhan
SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

"""Public surface: `from routers.admin import router` (and test helpers)."""

from dependencies import trigger_graceful_restart as trigger_graceful_restart

from .helpers import (
    BACKUP_DIR,
    _DOTENV_PATH,
    _apply_config_side_effects,
    _backup_running,
    _couple_embeddings_auto_on_enable,
    _job_is_disabled,
    _propagate_to_settings,
)
from .router import router

# Side-effect registration — order must match pre-split OpenAPI path order.
from . import system as system  # noqa: F401
from . import tokens as tokens  # noqa: F401
from . import storage as storage  # noqa: F401
from . import data_ops as data_ops  # noqa: F401
from . import config as config  # noqa: F401
from . import webhooks as webhooks  # noqa: F401
from . import database as database  # noqa: F401
from . import jobs as jobs  # noqa: F401
from . import catchup as catchup  # noqa: F401
from . import feeds as feeds  # noqa: F401
from . import webhooks_logs as webhooks_logs  # noqa: F401
from . import ai_ops as ai_ops  # noqa: F401
from . import diagnostics as diagnostics  # noqa: F401

from .config import _get_config_response
from .jobs import _JOB_RUN_MAP

__all__ = [
    "router",
    "BACKUP_DIR",
    "_DOTENV_PATH",
    "_JOB_RUN_MAP",
    "_apply_config_side_effects",
    "_backup_running",
    "_couple_embeddings_auto_on_enable",
    "_get_config_response",
    "_job_is_disabled",
    "_propagate_to_settings",
    "trigger_graceful_restart",
]
