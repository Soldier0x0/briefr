"""ML assist (V1.3 Theme 7) — env-gated, CPU-only, scheduler-side.

Every module here follows the ML placement rules in docs/OPERATIONS.md:
disabled by default, never on the request path (model inference runs in
scheduler jobs only), and a deterministic fallback keeps the tool fully
functional when ML is off.

Copyright © 2026 Sai Harsha Vardhan
SPDX-License-Identifier: Apache-2.0
"""
